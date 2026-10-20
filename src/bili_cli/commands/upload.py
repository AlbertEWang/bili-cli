"""bili upload: publish videos and track their review status.

Uploading goes through bilibili-api's VideoUploader with a hand-built meta
dict, because VideoMeta cannot express newer submit fields such as the
creation statement ("含AI生成内容"), private visibility or the new zone ID.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import typer
from bilibili_api import Credential, Picture
from bilibili_api import creative_center as cc
from bilibili_api import video_uploader as vu
from bilibili_api.utils.network import Api

from .. import config, guard, output
from ..errors import BiliError
from ..runtime import CST, iso_time, parse_timestamp, read_text, run, web_client

app = typer.Typer(help="视频投稿与稿件状态。", no_args_is_help=True)

PREDICT_URL = "https://member.bilibili.com/x/vupre/web/archive/types/predict"
PREUPLOAD_URL = "https://member.bilibili.com/preupload"
ZONES_URL = "https://member.bilibili.com/x/vupre/web/archive/human/type2/list"
# bilibili-api calls this with `t=`, which the server ignores; the parameter is `tag`.
TAG_CHECK_URL = "https://member.bilibili.com/x/vupre/web/topic/tag/check"
ARCHIVE_VIEW_URL = "https://member.bilibili.com/x/vupre/web/archive/view"
# Chapter endpoints, as used by B 站's player/editor bundle (scene=chapter).
CHAPTER_RULE_URL = "https://member.bilibili.com/x/web/viewpoint/rule"
CHAPTER_SUBMIT_URL = "https://member.bilibili.com/x/web/card/submit"
ALLCARDS_URL = "https://member.bilibili.com/x/web/allcards"
CARD_TYPE_CHAPTER = 2

TITLE_MAX = 80
DESC_MAX = 2000
DYNAMIC_MAX = 233
TAGS_MAX = 10
SCHEDULE_MIN_SECONDS = 2 * 3600  # Bilibili accepts scheduled publishing 2 h to 15 days ahead
SCHEDULE_MAX_SECONDS = 15 * 24 * 3600

# creation_statement ids used by the web uploader
STATEMENT_NONE = -1
STATEMENT_AI = 1

STATUS_FILTERS = {
    "all": cc.UploadManagerStatus.ALL,
    "published": cc.UploadManagerStatus.PUBED,
    "reviewing": cc.UploadManagerStatus.IS_PUBING,
    "rejected": cc.UploadManagerStatus.NOT_PUBED,
}


async def _predict_zone(cred: Credential, title: str) -> dict[str, Any] | None:
    """Ask Bilibili which zone fits the title, like the web uploader does."""
    async with web_client(cred, referer="https://member.bilibili.com/platform/upload/video/frame") as client:
        resp = await client.post(
            PREDICT_URL,
            params={"csrf": cred.bili_jct, "ts": int(time.time() * 1000)},
            files={"filename": (None, ""), "title": (None, title)},
        )
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data") or []
    if body.get("code") != 0 or not data:
        return None
    # Two independent guesses: the legacy zone (tid, still required by submit)
    # and the new zone (human_type2), which is what viewers see nowadays.
    first = data[0]
    human = first.get("human_type") or {}
    return {
        "tid": first.get("id"),
        "tid_name": f"{first.get('parent_name')} / {first.get('name')}",
        "zone": human.get("id"),
        "zone_name": human.get("name"),
    }


async def _zones(cred: Credential) -> list[dict[str, Any]]:
    async with web_client(cred, referer="https://member.bilibili.com/") as client:
        resp = await client.get(ZONES_URL)
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data") or {}
    return [{"id": z.get("id"), "name": z.get("name")} for z in (data.get("type_list") or body.get("type_list") or [])]


async def _check_tags(cred: Credential, tags: list[str]) -> list[str]:
    """Return the tags Bilibili rejects outright (it may still drop others after submit)."""
    bad = []
    for t in tags:
        res = await Api(url=TAG_CHECK_URL, method="GET", verify=True, credential=cred, ignore_code=True).update_params(tag=t).result
        if res.get("code") != 0:
            bad.append(t)
    return bad


async def _preflight(cred: Credential, video: Path) -> None:
    """Ask for an upload slot first, so a refusal comes back with Bilibili's reason.

    bilibili-api turns a refused preupload into a bare "HTTP 406"; the body
    actually says why, e.g. code 601 with a v_voucher when the account must
    pass a verification challenge (common for new accounts).
    """
    async with web_client(cred, referer="https://member.bilibili.com/") as client:
        resp = await client.get(
            PREUPLOAD_URL,
            params={"profile": "ugcfx/bup", "name": video.name, "size": video.stat().st_size, "r": "upos", "ssl": "0", "version": "2.14.0", "build": "2100400"},
        )
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code < 400 and body.get("OK") == 1:
        return
    message = body.get("message") or body.get("info") or f"HTTP {resp.status_code}"
    detail = {"bili_code": body.get("code"), "http_status": resp.status_code}
    if (body.get("detail") or {}).get("v_voucher"):
        raise BiliError(
            "captcha_required",
            f"B 站拒绝了上传：{message}",
            hint="账号触发了风控验证。请人类在网页端 https://member.bilibili.com/platform/upload/video/frame 手动上传一次并完成验证，或过一段时间再试；新号较常见。",
            detail=detail,
        )
    raise BiliError("risk_control" if resp.status_code in (406, 412) else "api_error", f"B 站拒绝了上传：{message}", detail=detail)


def _extract_cover(video: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise BiliError("invalid_argument", "未指定 --cover，且系统中没有 ffmpeg，无法自动截取封面。", hint="用 --cover 指定封面图片，或安装 ffmpeg。")
    out = Path(tempfile.mkdtemp(prefix="bili-cover-")) / "cover.jpg"
    for seek in ("3", "0"):  # very short videos have no frame at 3 s
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", seek, "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)],
            capture_output=True,
        )
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
    raise BiliError("invalid_argument", f"无法从视频中截取封面：{proc.stderr.decode(errors='ignore')[-300:]}", hint="用 --cover 指定封面图片。")


def _parse_schedule(value: str | None) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise BiliError("invalid_argument", f"--schedule 需要 ISO 时间，如 2026-10-21T20:00，收到 {value!r}。") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)  # Bilibili users think in Beijing time
    ts = int(dt.timestamp())
    delta = ts - time.time()
    if not SCHEDULE_MIN_SECONDS <= delta <= SCHEDULE_MAX_SECONDS:
        raise BiliError("invalid_argument", "定时发布时间必须在 2 小时到 15 天之后。", detail={"schedule": iso_time(ts)})
    return ts


def _progress(uploader: vu.VideoUploader) -> None:
    """Upload progress for humans, on stderr only."""

    def on_chunk(data: dict) -> None:
        done, total = data.get("chunk_number", 0) + 1, data.get("total_chunk_count", 0)
        if total:
            sys.stderr.write(f"\r上传中 {done}/{total} 块 ({done * 100 // total}%)")
            sys.stderr.flush()

    uploader.add_event_listener(vu.VideoUploaderEvents.AFTER_CHUNK.value, on_chunk)
    uploader.add_event_listener(vu.VideoUploaderEvents.AFTER_PAGE.value, lambda d: output.info("\n分 P 上传完成"))
    uploader.add_event_listener(vu.VideoUploaderEvents.PRE_SUBMIT.value, lambda d: output.info("正在提交稿件…"))


@app.command("video")
def video_(
    files: list[Path] = typer.Argument(..., help="视频文件；传多个即为多 P，按顺序排列。"),
    title: str = typer.Option(..., "--title", help=f"标题，最多 {TITLE_MAX} 字。"),
    tag: list[str] = typer.Option(..., "--tag", help=f"标签，可重复传入，1 到 {TAGS_MAX} 个。"),
    desc: Optional[str] = typer.Option(None, "--desc", help=f"简介，最多 {DESC_MAX} 字。"),
    desc_file: Optional[Path] = typer.Option(None, "--desc-file", help="从文件读取简介，`-` 表示 stdin。"),
    cover: Optional[Path] = typer.Option(None, "--cover", help="封面图片；不传则用 ffmpeg 从视频截取一帧。"),
    cover43: Optional[Path] = typer.Option(
        None, "--cover43", help="4:3 封面（手机端推荐流用这一张）；不传则由 B 站从横版封面处理。"
    ),
    zone_id: Optional[int] = typer.Option(
        None, "--zone", help="新版分区 ID（见 `bili upload zones`）；不传则按标题自动预测，预测不一定准。"
    ),
    tid: Optional[int] = typer.Option(None, "--tid", help="旧版分区 ID；不传则按标题自动预测。"),
    repost: Optional[str] = typer.Option(None, "--repost", help="转载稿件的来源链接；不传即为自制。"),
    ai_declare: bool = typer.Option(
        True, "--ai-declare/--no-ai-declare", help="勾选创作声明“含AI生成内容”。默认开启，关闭需显式传 --no-ai-declare。"
    ),
    private: bool = typer.Option(False, "--private", help="仅自己可见（适合测试）。"),
    schedule: Optional[str] = typer.Option(None, "--schedule", help="定时发布，ISO 时间（默认北京时间），需在 2 小时到 15 天之后。"),
    dynamic: Optional[str] = typer.Option(None, "--dynamic", help=f"同步发布的粉丝动态文字，最多 {DYNAMIC_MAX} 字。"),
    no_reprint: bool = typer.Option(False, "--no-reprint", help="声明未经授权禁止转载。"),
    close_comments: bool = typer.Option(False, "--close-comments", help="关闭评论。"),
    close_danmaku: bool = typer.Option(False, "--close-danmaku", help="关闭弹幕。"),
    line: Optional[str] = typer.Option(None, "--line", help="上传线路：bda2 / qn / ws / bldsa；不传则自动测速。"),
) -> None:
    """上传视频并投稿。默认勾选“含AI生成内容”声明。上传可能耗时较久，进度输出在 stderr。"""

    async def body():
        cred = config.require_credential()
        for f in files:
            if not f.is_file():
                raise BiliError("invalid_argument", f"视频文件不存在：{f}")
        if cover is not None and not cover.is_file():
            raise BiliError("invalid_argument", f"封面文件不存在：{cover}")
        if cover43 is not None and not cover43.is_file():
            raise BiliError("invalid_argument", f"4:3 封面文件不存在：{cover43}")
        if not title.strip() or len(title) > TITLE_MAX:
            raise BiliError("invalid_argument", f"标题需为 1 到 {TITLE_MAX} 字。")
        tags = [t.strip() for t in tag if t.strip()]
        if not 1 <= len(tags) <= TAGS_MAX:
            raise BiliError("invalid_argument", f"标签需为 1 到 {TAGS_MAX} 个。")
        description = read_text(desc, desc_file) if (desc is not None or desc_file is not None) else ""
        if len(description) > DESC_MAX:
            raise BiliError("invalid_argument", f"简介最多 {DESC_MAX} 字。")
        if dynamic and len(dynamic) > DYNAMIC_MAX:
            raise BiliError("invalid_argument", f"粉丝动态最多 {DYNAMIC_MAX} 字。")
        line_enum = None
        if line:
            try:
                line_enum = vu.Lines(line)
            except ValueError as exc:
                raise BiliError("invalid_argument", "--line 只能是 bda2 / qn / ws / bldsa。") from exc
        dtime = _parse_schedule(schedule)

        zone: dict[str, Any] = {"tid": tid, "tid_name": None, "zone": zone_id, "zone_name": None}
        if tid is None or zone_id is None:
            predicted = await _predict_zone(cred, title)
            if predicted is None:
                raise BiliError("invalid_argument", "无法自动预测分区。", hint="用 --tid 和 --zone 手动指定分区。")
            if tid is None:
                zone["tid"], zone["tid_name"] = predicted["tid"], predicted["tid_name"]
            if zone_id is None:
                zone["zone"], zone["zone_name"] = predicted["zone"], predicted["zone_name"]
        if zone_id is not None:
            known = {z["id"]: z["name"] for z in await _zones(cred)}
            if zone_id not in known:
                raise BiliError("invalid_argument", f"未知的分区 ID {zone_id}。", hint="运行 `bili upload zones` 查看可用分区。")
            zone["zone_name"] = known[zone_id]
        zone["predicted"] = zone_id is None
        bad_tags = await _check_tags(cred, tags)
        if bad_tags:
            raise BiliError("invalid_argument", f"B 站不接受这些标签：{', '.join(bad_tags)}", detail={"rejected_tags": bad_tags})

        meta: dict[str, Any] = {
            "title": title,
            "copyright": 2 if repost else 1,
            "tid": zone["tid"],
            "tag": ",".join(tags),
            "desc_format_id": 9999,
            "desc": description,
            "recreate": -1,
            "dynamic": dynamic or "",
            "interactive": 0,
            "act_reserve_create": 0,
            "no_disturbance": 0,
            "no_reprint": 1 if no_reprint else 0,
            "subtitle": {"open": 0, "lan": ""},
            "dolby": 0,
            "lossless_music": 0,
            "up_selection_reply": False,
            "up_close_reply": close_comments,
            "up_close_danmu": close_danmaku,
            "web_os": 1,
            "is_only_self": 1 if private else 0,
            "creation_statement": {"id": STATEMENT_AI if ai_declare else STATEMENT_NONE},
        }
        if zone.get("zone"):
            meta["human_type2"] = zone["zone"]
        if repost:
            meta["source"] = repost
        if dtime:
            meta["dtime"] = dtime

        summary = {
            "files": [str(f) for f in files],
            "title": title,
            "tags": tags,
            "zone": zone,
            "ai_declare": ai_declare,
            "private": private,
            "schedule": iso_time(dtime),
            "copyright": "repost" if repost else "original",
            "cover": str(cover) if cover else "auto (ffmpeg)",
            "cover43": str(cover43) if cover43 else None,
        }
        if output.settings.dry_run:
            return {"dry_run": True, "action": "upload.video", "params": summary, "meta": meta}

        guard.check("upload")
        await _preflight(cred, files[0])
        cover_path = cover or _extract_cover(files[0])
        if cover43:
            # same image endpoint as the main cover; the archive keeps it in a separate `cover43` field
            meta["cover43"] = await vu.upload_cover(Picture.from_file(str(cover43)), cred)
        pages = [vu.VideoUploaderPage(path=str(f), title=f.stem if len(files) > 1 else title) for f in files]
        uploader = vu.VideoUploader(pages, meta, cred, cover=Picture.from_file(str(cover_path)), line=line_enum)
        if sys.stderr.isatty():
            _progress(uploader)
        res = await uploader.start()
        result = {"bvid": res.get("bvid"), "aid": res.get("aid"), "url": f"https://www.bilibili.com/video/{res.get('bvid')}"}
        guard.record("upload", summary, result)
        return {
            **result,
            **summary,
            "next": f"稿件需要审核，用 `bili upload status {res.get('bvid')}` 查看进度。",
        }

    run(body)


def _archive(a: dict[str, Any]) -> dict[str, Any]:
    arc = a.get("Archive") or {}
    stat = a.get("stat") or {}
    return {
        "bvid": arc.get("bvid"),
        "aid": arc.get("aid"),
        "title": arc.get("title"),
        "state": arc.get("state"),
        "state_desc": arc.get("state_desc"),
        "published": arc.get("state") == 0,
        "reject_reason": arc.get("reject_reason") or None,
        "publish_time": iso_time(arc.get("ptime")),
        "scheduled_time": iso_time(arc.get("dtime")),
        "stat": {k: stat.get(k) for k in ("view", "danmaku", "reply", "favorite", "coin", "share", "like")},
    }


@app.command("list")
def list_(
    status: str = typer.Option("all", "--status", help="all / published / reviewing / rejected"),
    page: int = typer.Option(1, "--page", min=1, help="页码，从 1 开始。"),
    size: int = typer.Option(10, "--size", min=1, max=50, help="每页条数。"),
) -> None:
    """我的稿件列表（按投稿时间倒序），含审核状态与数据。"""

    async def body():
        if status not in STATUS_FILTERS:
            raise BiliError("invalid_argument", f"--status 只能是 {' / '.join(STATUS_FILTERS)} 之一。")
        cred = config.require_credential()
        data = await cc.get_video_upload_manager_info(
            cred, pn=page, ps=size, order=cc.UploadManagerOrder.SENDDATE, status=STATUS_FILTERS[status]
        )
        if output.settings.raw:
            return data
        counts = data.get("class") or {}
        return {
            "counts": {"published": counts.get("pubed"), "reviewing": counts.get("is_pubing"), "rejected": counts.get("not_pubed")},
            "page": page,
            "items": [_archive(a) for a in data.get("arc_audits") or []],
        }

    run(body)


@app.command()
def status(bvid: str = typer.Argument(..., help="稿件 BV 号。")) -> None:
    """查看一个稿件的审核状态，以及 B 站实际记录的标签、分区、声明与可见性（可能和提交时不同）。"""

    async def body():
        cred = config.require_credential()
        async with web_client(cred, referer="https://member.bilibili.com/") as client:
            resp = await client.get(ARCHIVE_VIEW_URL, params={"bvid": bvid})
            resp.raise_for_status()
            res = resp.json()
        if res.get("code") != 0:
            from bilibili_api.exceptions import ResponseCodeException

            raise ResponseCodeException(res.get("code"), res.get("message"), res)
        data = res.get("data") or {}
        if output.settings.raw:
            return data
        arc = data.get("archive") or {}
        statement = arc.get("creation_statement") or {}
        human = arc.get("human_type2") or {}
        return {
            "bvid": arc.get("bvid"),
            "aid": arc.get("aid"),
            "title": arc.get("title"),
            "state": arc.get("state"),
            "state_desc": arc.get("state_desc"),
            "reject_reason": arc.get("reject_reason") or None,
            "private": arc.get("is_only_self") == 1,
            "ai_declare": statement.get("id") == STATEMENT_AI,
            "creation_statement": statement.get("content"),
            "tags": [t for t in (arc.get("tag") or "").split(",") if t],
            "zone": {"tid": arc.get("tid"), "zone": human.get("id"), "zone_name": human.get("name")},
            "publish_time": iso_time(arc.get("ptime")),
            "scheduled_time": iso_time(arc.get("dtime")),
            "pages": [
                {"cid": v.get("cid"), "title": v.get("title"), "status_desc": v.get("status_desc") or None, "fail_desc": v.get("fail_desc") or None}
                for v in data.get("videos") or []
            ],
            "url": f"https://www.bilibili.com/video/{arc.get('bvid')}",
        }

    run(body)


chapters = typer.Typer(help="分段章节（进度条上的章节标题）：查看、设置、清空自己稿件的章节。", no_args_is_help=True)
app.add_typer(chapters, name="chapters")


def parse_chapter_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Each line is '<time> <title>', e.g. '01:30 正片开始' (the format of the web editor's text mode)."""
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        stamp, _, title = line.partition(" ")
        if not title.strip():
            raise BiliError("invalid_argument", f"章节缺少标题：{line!r}，格式应为 “01:30 标题”。")
        out.append((parse_timestamp(stamp), title.strip()))
    return out


def build_chapters(items: list[tuple[int, str]], duration: int, limit: int, min_seconds: int) -> list[dict[str, Any]]:
    if not items:
        raise BiliError("invalid_argument", "至少需要一个章节。")
    if len(items) > limit:
        raise BiliError("invalid_argument", f"最多 {limit} 个章节，收到 {len(items)} 个。")
    items = sorted(items)
    if items[0][0] != 0:
        raise BiliError("invalid_argument", "第一个章节必须从 0:00 开始。")
    cards = []
    for i, (start, title) in enumerate(items):
        end = items[i + 1][0] if i + 1 < len(items) else duration
        if end > duration or start >= duration:
            raise BiliError("invalid_argument", f"章节 {title!r} 的时间超出视频时长 {duration} 秒。")
        if end - start < min_seconds:
            raise BiliError("invalid_argument", f"章节 {title!r} 太短，每个章节至少 {min_seconds} 秒。")
        cards.append({"from": start, "to": end, "content": title})
    return cards


async def _chapter_rules(client, bvid: str, aid: int, cid: int) -> dict[str, Any]:
    resp = await client.get(CHAPTER_RULE_URL, params={"bvid": bvid, "aid": aid, "cid": cid})
    resp.raise_for_status()
    return ((resp.json().get("data") or {}).get("chapters")) or {}


async def _submit_chapters(client, cred: Credential, aid: int, cid: int, cards: list[dict]) -> None:
    resp = await client.post(
        CHAPTER_SUBMIT_URL,
        data={"aid": aid, "cid": cid, "type": CARD_TYPE_CHAPTER, "cards": json.dumps(cards, ensure_ascii=False), "permanent": 0, "csrf": cred.bili_jct},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        from bilibili_api.exceptions import ResponseCodeException

        raise ResponseCodeException(body.get("code"), body.get("message"), body)


@chapters.command("show")
def chapters_show(
    video_id: str = typer.Argument(..., help="自己的稿件：BV 号、av 号或链接。"),
    page: int = typer.Option(1, "--page", "-p", min=1, help="分 P 序号，从 1 开始。"),
) -> None:
    """查看自己稿件里设置的章节（含审核中的）及章节规则。"""

    async def body():
        from .danmaku import own_video_page

        cred = config.require_credential()
        info, pg = await own_video_page(video_id, page, cred)
        async with web_client(cred, referer="https://www.bilibili.com/") as client:
            rules = await _chapter_rules(client, info["bvid"], info["aid"], pg["cid"])
            resp = await client.get(ALLCARDS_URL, params={"aid": info["aid"], "cid": pg["cid"]})
            resp.raise_for_status()
            data = resp.json().get("data") or {}
        catalog = next((c for c in data.get("catalog") or [] if c.get("type") == CARD_TYPE_CHAPTER), None)
        return {
            "bvid": info["bvid"],
            "page": page,
            "rules": {"max_chapters": rules.get("limit"), "min_seconds": rules.get("stay"), "min_video_minutes": rules.get("first_min_duration")},
            "chapters": [
                {"from": c.get("from"), "to": c.get("to"), "title": c.get("content")} for c in (catalog or {}).get("cards") or []
            ],
            "updated_at": (catalog or {}).get("mtime"),
        }

    run(body)


@chapters.command("set")
def chapters_set(
    video_id: str = typer.Argument(..., help="自己的稿件：BV 号、av 号或链接。"),
    chapter: list[str] = typer.Option([], "--chapter", "-c", help="章节，格式“时间 标题”，如 “0:00 开场”，可重复传入。"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="从文件读取章节，每行“时间 标题”，`-` 表示 stdin。"),
    page: int = typer.Option(1, "--page", "-p", min=1, help="分 P 序号，从 1 开始。"),
) -> None:
    """设置分段章节（会整体替换已有章节）。每个章节到下一个章节开始为止，最后一个到视频结尾。"""

    async def body():
        from .danmaku import own_video_page

        cred = config.require_credential()
        lines = list(chapter)
        if file is not None:
            lines += read_text(None, file).splitlines()
        if not lines:
            raise BiliError("invalid_argument", "用 --chapter 或 --file 提供章节。")
        items = parse_chapter_lines(lines)
        info, pg = await own_video_page(video_id, page, cred)
        duration = int(pg.get("duration") or 0)
        async with web_client(cred, referer="https://www.bilibili.com/") as client:
            rules = await _chapter_rules(client, info["bvid"], info["aid"], pg["cid"])
            min_minutes = rules.get("first_min_duration") or 0
            if duration < min_minutes * 60:
                raise BiliError("invalid_argument", f"视频需长于 {min_minutes} 分钟才能添加章节。")
            cards = build_chapters(items, duration, rules.get("limit") or 10, rules.get("stay") or 0)
            params = {"bvid": info["bvid"], "page": page, "chapters": [{"from": c["from"], "to": c["to"], "title": c["content"]} for c in cards]}
            if output.settings.dry_run:
                return {"dry_run": True, "action": "upload.chapters.set", "params": params}
            guard.check("profile")
            await _submit_chapters(client, cred, info["aid"], pg["cid"], cards)
        guard.record("profile", params, "ok")
        return {**params, "updated": True, "note": "章节需要审核，通过后才会显示在进度条上。"}

    run(body)


@chapters.command("clear")
def chapters_clear(
    video_id: str = typer.Argument(..., help="自己的稿件：BV 号、av 号或链接。"),
    page: int = typer.Option(1, "--page", "-p", min=1, help="分 P 序号，从 1 开始。"),
) -> None:
    """清空稿件的分段章节。"""

    async def body():
        from .danmaku import own_video_page

        cred = config.require_credential()
        info, pg = await own_video_page(video_id, page, cred)
        if output.settings.dry_run:
            return {"dry_run": True, "action": "upload.chapters.clear", "params": {"bvid": info["bvid"], "page": page}}
        guard.check("profile")
        async with web_client(cred, referer="https://www.bilibili.com/") as client:
            # The web editor deletes chapters by submitting the remaining ones; none left = cleared.
            await _submit_chapters(client, cred, info["aid"], pg["cid"], [])
        guard.record("profile", {"bvid": info["bvid"], "chapters": []}, "ok")
        return {"bvid": info["bvid"], "page": page, "cleared": True}

    run(body)


@app.command()
def zones() -> None:
    """列出新版分区（投稿用 `--zone` 指定）。"""

    async def body():
        return {"zones": await _zones(config.require_credential())}

    run(body)
