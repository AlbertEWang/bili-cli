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


# x/space/wap/relation: attribute 0 = not following, 1 = following quietly, 2 = following, 6 = mutual, 128 = blocked
_ATTRS = {0: "none", 1: "following", 2: "following", 6: "mutual", 128: "blocked"}


async def _relation_with(u: user.User) -> dict[str, Any]:
    data = await u.get_relation()
    mine = (data.get("relation") or {}).get("attribute") or 0
    theirs = (data.get("be_relation") or {}).get("attribute") or 0
    return {"i_follow": mine in (1, 2, 6), "follows_me": theirs in (1, 2, 6), "relation": _ATTRS.get(mine, str(mine))}


async def _set_follow(who: str, follow: bool) -> dict[str, Any]:
    from .. import guard

    cred = config.require_credential()
    mid = await resolve_mid(who)
    if str(mid) == str(cred.dedeuserid):
        raise BiliError("invalid_argument", "不能关注 / 取关自己。")
    u = user.User(mid, credential=cred)
    before = await _relation_with(u)
    if before["relation"] == "blocked":
        raise BiliError("invalid_argument", f"你已把 {mid} 拉黑，先在网页上解除拉黑。")
    params = {"mid": mid, "follow": follow}
    if before["i_follow"] == follow:
        return {**params, "changed": False, **before}
    if output.settings.dry_run:
        return {"dry_run": True, "action": "user.follow" if follow else "user.unfollow", "params": params}
    guard.check("follow")
    await u.modify_relation(user.RelationType.SUBSCRIBE if follow else user.RelationType.UNSUBSCRIBE)
    guard.record("follow", params, "ok")
    return {**params, "changed": True, **await _relation_with(u)}


@app.command()
def follow(who: str = USER_ARG) -> None:
    """关注一个用户（已关注时什么也不做）。本地限制每小时最多 20 次关注 / 取关。"""
    run(lambda: _set_follow(who, True))


@app.command()
def unfollow(who: str = USER_ARG) -> None:
    """取消关注一个用户（没关注时什么也不做）。"""
    run(lambda: _set_follow(who, False))


@app.command()
def following(
    page: int = typer.Option(1, "--page", min=1, help="页码，从 1 开始。"),
    size: int = typer.Option(50, "--size", min=1, max=50, help="每页条数。"),
) -> None:
    """我关注的人，按关注时间从新到旧。"""

    async def body():
        cred = config.require_credential()
        data = await user.User(int(cred.dedeuserid), credential=cred).get_followings(pn=page, ps=size)
        if output.settings.raw:
            return data
        return {
            "page": page,
            "total": data.get("total"),
            "items": [
                {
                    "mid": f.get("mid"),
                    "name": f.get("uname"),
                    "sign": f.get("sign") or None,
                    "mutual": f.get("attribute") == 6,
                    "followed_at": iso_time(f.get("mtime")),
                }
                for f in data.get("list") or []
            ],
        }

    run(body)
