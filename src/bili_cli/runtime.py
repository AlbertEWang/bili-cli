"""Glue between synchronous Typer commands and the async bilibili-api."""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

from . import output
from .errors import BiliError, from_exception

T = TypeVar("T")

CST = timezone(timedelta(hours=8))

# For requests made with httpx directly (endpoints bilibili-api does not wrap);
# without a browser UA and Referer Bilibili answers HTTP 412.
WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def web_client(cred=None, referer: str | None = None, timeout: float = 20):
    """An httpx client that looks like the web app, optionally logged in."""
    import httpx

    headers = dict(WEB_HEADERS)
    if referer:
        headers["Referer"] = referer
    cookies = {}
    if cred is not None:
        cookies = {
            k: v
            for k, v in {
                "SESSDATA": cred.sessdata,
                "bili_jct": cred.bili_jct,
                "DedeUserID": cred.dedeuserid,
                "buvid3": cred.buvid3,
                "buvid4": cred.buvid4,
            }.items()
            if v
        }
    return httpx.AsyncClient(headers=headers, cookies=cookies, timeout=timeout)


def run(coro_fn: Callable[[], Awaitable[Any]]) -> None:
    """Run a command body, print its result as JSON, and map every failure to a BiliError."""
    if sys.platform == "win32":
        # The proactor loop spams "Event loop is closed" on exit with some HTTP clients.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        result = asyncio.run(coro_fn())
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001 - every failure must become JSON
        import typer

        if isinstance(exc, (typer.Exit, SystemExit)):
            raise
        output.fail(from_exception(exc))
    else:
        if result is not None:
            output.success(result)


_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_AV_RE = re.compile(r"(?:^|/|\b)av(\d+)", re.IGNORECASE)


def parse_video_id(value: str) -> dict[str, Any]:
    """Accept BV号, av号 (av170001 / 170001) or a video URL; return kwargs for bilibili_api.video.Video."""
    value = value.strip()
    m = _BV_RE.search(value)
    if m:
        return {"bvid": m.group(1)}
    m = _AV_RE.search(value)
    if m:
        return {"aid": int(m.group(1))}
    if value.isdigit():
        return {"aid": int(value)}
    raise BiliError("invalid_argument", f"无法识别的视频 ID：{value!r}，支持 BV 号、av 号或视频链接。")


def iso_time(ts: int | float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, CST).isoformat()


_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    import html

    return html.unescape(_TAG_RE.sub("", text or ""))


def read_text(text: str | None, file: Path | None) -> str:
    """Resolve message text from a positional argument, --file PATH, or --file - (stdin)."""
    if text is not None and file is not None:
        raise BiliError("invalid_argument", "文本参数和 --file 只能二选一。")
    if file is not None:
        if str(file) == "-":
            content = sys.stdin.buffer.read().decode("utf-8")
        else:
            try:
                content = file.read_text(encoding="utf-8")
            except OSError as exc:
                raise BiliError("invalid_argument", f"无法读取文件 {file}：{exc}") from exc
    elif text is not None:
        content = text
    else:
        raise BiliError("invalid_argument", "缺少文本内容：传入文本参数或使用 --file。")
    content = content.strip()
    if not content:
        raise BiliError("invalid_argument", "文本内容为空。")
    return content


def parse_timestamp(value: str) -> int:
    """'90', '1:30' or '0:01:30' -> seconds."""
    parts = value.strip().replace("：", ":").split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError as exc:
        raise BiliError("invalid_argument", f"无法识别的时间 {value!r}，请用 秒、分:秒 或 时:分:秒。") from exc
    if len(nums) > 3 or any(n < 0 for n in nums):
        raise BiliError("invalid_argument", f"无法识别的时间 {value!r}。")
    total = 0
    for n in nums:
        total = total * 60 + n
    return total
