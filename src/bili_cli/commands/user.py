"""bili user: look up any user's profile and uploads (for competitor research and replying with context)."""

from __future__ import annotations

from typing import Any

import typer
from bilibili_api import search, user

from .. import config, output
from ..errors import BiliError
from ..runtime import iso_time, run, strip_html

app = typer.Typer(help="查看任意用户：资料、粉丝数、投稿列表。", no_args_is_help=True)

USER_ARG = typer.Argument(..., help="UID，或完整昵称（会用搜索找到昵称完全一致的用户）。")
VIDEO_ORDERS = {"new": user.VideoOrder.PUBDATE, "views": user.VideoOrder.VIEW, "favorites": user.VideoOrder.FAVORITE}


async def resolve_mid(who: str) -> int:
    """A UID as-is; otherwise the user whose current nickname matches exactly."""
    who = who.strip().lstrip("@")
    if who.isdigit():
        return int(who)
    data = await search.search_by_type(who, search_type=search.SearchObjectType.USER)
    for r in data.get("result") or []:
        if strip_html(r.get("uname")) == who:
            return int(r["mid"])
    raise BiliError("not_found", f"找不到昵称为 {who!r} 的用户。", hint=f"用 `bili search user {who}` 找到 UID 再传入。")


@app.command()
def info(who: str = USER_ARG) -> None:
    """用户资料：昵称、签名、等级、认证、粉丝 / 关注数、总播放与获赞、直播间。"""

    async def body():
        u = user.User(await resolve_mid(who), credential=config.optional_credential())
        data = await u.get_user_info()
        rel = await u.get_relation_info()
        try:
            up = await u.get_up_stat()  # needs login; skip quietly when anonymous
        except Exception:  # noqa: BLE001
            up = {}
        if output.settings.raw:
            return {"info": data, "relation": rel, "up_stat": up}
        official = data.get("official") or {}
        live = data.get("live_room") or {}
        out: dict[str, Any] = {
            "mid": data.get("mid"),
            "name": data.get("name"),
            "sign": data.get("sign") or None,
            "level": data.get("level"),
            "official": official.get("title") or None,
            "fans": rel.get("follower"),
            "following": rel.get("following"),
            "url": f"https://space.bilibili.com/{data.get('mid')}",
        }
        if up:
            out["total_views"] = (up.get("archive") or {}).get("view")
            out["total_likes"] = up.get("likes")
        if live.get("roomid"):
            out["live"] = {"live_now": live.get("liveStatus") == 1, "title": live.get("title"), "url": f"https://live.bilibili.com/{live.get('roomid')}"}
        out["videos_with"] = f"bili user videos {data.get('mid')}"
        return out

    run(body)


@app.command()
def videos(
    who: str = USER_ARG,
    order: str = typer.Option("new", "--order", help="排序：new（最新）/ views（最多播放）/ favorites（最多收藏）。"),
    keyword: str = typer.Option("", "--keyword", "-k", help="只看标题含关键词的投稿，如某个系列名。"),
    page: int = typer.Option(1, "--page", min=1, help="页码，从 1 开始。"),
    size: int = typer.Option(20, "--size", min=1, max=50, help="每页条数。"),
) -> None:
    """用户的投稿列表，含播放、评论、弹幕数，适合找爆款或追某个系列。"""

    async def body():
        if order not in VIDEO_ORDERS:
            raise BiliError("invalid_argument", f"--order 只能是 {' / '.join(VIDEO_ORDERS)} 之一。")
        mid = await resolve_mid(who)
        data = await user.User(mid, credential=config.optional_credential()).get_videos(
            pn=page, ps=size, keyword=keyword, order=VIDEO_ORDERS[order]
        )
        if output.settings.raw:
            return data
        return {
            "mid": mid,
            "page": page,
            "total": (data.get("page") or {}).get("count"),
            "items": [
                {
                    "bvid": v.get("bvid"),
                    "title": v.get("title"),
                    "length": v.get("length"),
                    "play": v.get("play"),
                    "comment": v.get("comment"),
                    "danmaku": v.get("video_review"),
                    "pubdate": iso_time(v.get("created")),
                }
                for v in (data.get("list") or {}).get("vlist") or []
            ],
        }

    run(body)
