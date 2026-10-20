"""Turn a video into still images an agent can look at.

Two sources:
- preview: Bilibili's own seek-bar thumbnails (480x270 sprite sheets plus a
  timestamp index). No video download and no ffmpeg; the nearest thumbnail
  is used, typically a few seconds from the requested time.
- hd: ffmpeg seeks inside the DASH video stream (<= 720p, H.264) and grabs the
  exact frame. Only the bytes around each timestamp are fetched, ~3 s a frame.
"""

from __future__ import annotations

import asyncio
import bisect
import io
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import BiliError
from .runtime import WEB_HEADERS, web_client

MAX_PREVIEW_FRAMES = 100
MAX_HD_FRAMES = 30
HD_MAX_HEIGHT = 720
HD_CONCURRENCY = 1  # the CDN throttles parallel range requests: 6 frames took 18 s sequentially, 67 s with 3 at once
HD_FRAME_TIMEOUT = 60
SHEET_COLUMNS = 3
SHEET_TILE_WIDTH = 480


def plan_times(
    duration: float,
    count: int | None = None,
    every: float | None = None,
    at: list[float] | None = None,
    chapter_starts: list[float] | None = None,
) -> list[float]:
    """Pick sample times (seconds) within [0, duration)."""
    if duration <= 0:
        raise BiliError("invalid_argument", "无法获取视频时长。")
    if at:
        bad = [t for t in at if t >= duration]
        if bad:
            raise BiliError("invalid_argument", f"时间点超出视频时长 {int(duration)} 秒：{bad}")
        times = [float(t) for t in at]
    elif every:
        n = int(duration // every) + 1
        # skip the very first frame, which is often black
        times = [min(max(i * every, 1.0), duration - 0.5) for i in range(n)]
    elif chapter_starts is not None:
        if not chapter_starts:
            raise BiliError("not_found", "该视频没有分段章节。", hint="改用 --count 或 --every 采样。")
        times = [min(t + 3.0, duration - 0.5) for t in chapter_starts]
    else:
        n = count or 9
        times = [duration * (i + 0.5) / n for i in range(n)]
    return sorted({round(t, 2) for t in times})


def fmt_time(t: float) -> str:
    t = round(t, 2)
    frac = round(t % 1, 2)
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    sec = f"{s:02d}" + (f"{frac:.2f}".lstrip("0").rstrip("0") if frac else "")
    return f"{h}:{m:02d}:{sec}" if h else f"{m}:{sec}"


def frame_name(t: float) -> str:
    """frame_000090.jpg, or frame_000090_500.jpg for 90.5 s so sub-second frames don't overwrite each other."""
    ms = round(t * 1000) % 1000
    return f"frame_{int(t):06d}" + (f"_{ms:03d}" if ms else "") + ".jpg"


async def grab_preview(snapshot: dict[str, Any], times: list[float], out_dir: Path) -> list[dict[str, Any]]:
    from PIL import Image

    index: list[int] = snapshot.get("index") or []
    images: list[str] = snapshot.get("image") or []
    cols, rows = snapshot.get("img_x_len") or 10, snapshot.get("img_y_len") or 10
    w, h = snapshot.get("img_x_size"), snapshot.get("img_y_size")
    if not index or not images or not w or not h:
        raise BiliError("not_found", "该视频没有预览缩略图。", hint="改用 --quality hd（需要 ffmpeg）。")
    per_sheet = cols * rows
    count = min(len(index), len(images) * per_sheet)
    sheets: dict[int, Image.Image] = {}
    results = []
    async with web_client() as client:
        for t in times:
            k = max(0, min(bisect.bisect_right(index, t) - 1, count - 1))
            sheet_no, pos = divmod(k, per_sheet)
            if sheet_no not in sheets:
                url = images[sheet_no]
                resp = await client.get("https:" + url if url.startswith("//") else url)
                resp.raise_for_status()
                sheets[sheet_no] = Image.open(io.BytesIO(resp.content)).convert("RGB")
            x, y = (pos % cols) * w, (pos // cols) * h
            path = out_dir / frame_name(t)
            sheets[sheet_no].crop((x, y, x + w, y + h)).save(path, quality=90)
            results.append({"time": t, "actual_time": index[k], "path": str(path)})
    return results


def pick_stream(playurl: dict[str, Any]) -> dict[str, Any]:
    streams = (playurl.get("dash") or {}).get("video") or []
    h264 = [s for s in streams if str(s.get("codecs", "")).startswith("avc1")]
    pool = h264 or streams
    if not pool:
        raise BiliError("not_found", "没有可用的视频流。", hint="改用 --quality preview。")
    fitting = [s for s in pool if (s.get("height") or 0) <= HD_MAX_HEIGHT]
    return max(fitting, key=lambda s: s.get("height") or 0) if fitting else min(pool, key=lambda s: s.get("height") or 0)


async def grab_hd(playurl: dict[str, Any], times: list[float], out_dir: Path) -> list[dict[str, Any]]:
    if not shutil.which("ffmpeg"):
        raise BiliError("invalid_argument", "--quality hd 需要 ffmpeg。", hint="安装 ffmpeg，或改用 --quality preview。")
    stream = pick_stream(playurl)
    urls = [stream.get("baseUrl") or stream.get("base_url")] + list(stream.get("backupUrl") or stream.get("backup_url") or [])
    headers = "".join(f"{k}: {v}\r\n" for k, v in WEB_HEADERS.items())
    sem = asyncio.Semaphore(HD_CONCURRENCY)

    async def one(t: float) -> dict[str, Any]:
        path = out_dir / frame_name(t)
        err = b""
        async with sem:
            for url in filter(None, urls):
                # A thread rather than asyncio subprocesses: the selector loop used on Windows cannot spawn them.
                # -nostdin + DEVNULL: otherwise concurrent ffmpegs wait on the console for key presses.
                try:
                    proc = await asyncio.to_thread(
                        subprocess.run,
                        ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-headers", headers,
                         "-ss", f"{t:.2f}", "-i", url, "-frames:v", "1", "-q:v", "3", str(path)],
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        timeout=HD_FRAME_TIMEOUT,
                    )
                except subprocess.TimeoutExpired:
                    err = f"ffmpeg 超过 {HD_FRAME_TIMEOUT} 秒未完成".encode()
                    continue
                err = proc.stderr
                if proc.returncode == 0 and path.exists() and path.stat().st_size > 0:
                    return {"time": t, "actual_time": t, "path": str(path)}
            raise BiliError("network_error", f"截取 {fmt_time(t)} 的画面失败：{err.decode(errors='ignore')[-200:]}")

    results = await asyncio.gather(*(one(t) for t in times))
    return list(results)


def contact_sheet(frames: list[dict[str, Any]], path: Path) -> Path:
    """All frames on one image with timestamps, so an agent can take them in with a single look."""
    from PIL import Image, ImageDraw, ImageFont

    tiles = []
    for f in frames:
        img = Image.open(f["path"]).convert("RGB")
        ratio = SHEET_TILE_WIDTH / img.width
        tiles.append(img.resize((SHEET_TILE_WIDTH, int(img.height * ratio))))
    tile_h = max(t.height for t in tiles)
    cols = min(SHEET_COLUMNS, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * SHEET_TILE_WIDTH, rows * tile_h), "black")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    for i, (tile, f) in enumerate(zip(tiles, frames)):
        x, y = (i % cols) * SHEET_TILE_WIDTH, (i // cols) * tile_h
        sheet.paste(tile, (x, y))
        label = f"#{i + 1} {fmt_time(f['actual_time'])}"
        box = draw.textbbox((x + 6, y + 6), label, font=font)
        draw.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill="black")
        draw.text((x + 6, y + 6), label, fill="white", font=font)
    sheet.save(path, quality=88)
    return path
