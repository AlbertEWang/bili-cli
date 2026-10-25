import asyncio
import io
import json
from types import SimpleNamespace

import httpx
from PIL import Image

from bili_cli import frames as fr
from bili_cli import reactions as rx


def test_top_texts_groups_variants_and_drops_noise():
    top = rx.top_texts(["一眼万年", "一眼万年！", "一眼万年 ", "哈哈哈哈哈", "哈哈哈", "。", "1", "可爱"])
    assert top[0] == {"text": "一眼万年", "n": 3}
    assert top[1]["n"] == 2 and top[1]["text"].startswith("哈哈")
    assert all(t["text"] not in ("。", "1") for t in top)


def test_assign_credits_reactions_to_the_frame_they_react_to():
    # moments (time - 2 s): 5.5, 7, 9, 11, 0 -> the first frame owns everything before the 10 s midpoint
    dms = [(7.5, "第一"), (9, "第二"), (11, "第三"), (13, "第四"), (1, "开头")]
    out = rx.assign(dms, [5, 15], duration=20)
    assert [o["count"] for o in out] == [4, 1]
    assert out[1]["top"][0]["text"] == "第四"


def test_assign_ignores_moments_far_from_every_frame():
    out = rx.assign([(25, "x")], [5, 40], duration=60)  # moment 23: >8 s from both frames
    assert [o["count"] for o in out] == [0, 0]


def test_peaks_find_the_bursts_moved_back_by_the_typing_lag():
    dms = [(float(t), "普通") for t in range(33)]
    dms += [(25 + i / 30, "一眼万年") for i in range(60)]  # sent at 25-27 s, reacting to ~23-25 s
    dms += [(14 + i / 10, "可爱捏") for i in range(20)]
    pk = rx.peaks(dms, duration=33, n=3)
    assert len(pk) >= 2
    big = max(pk, key=lambda p: p["count"])
    assert 22.5 <= big["time"] <= 25.5 and big["top"][0]["text"] == "一眼万年"
    assert any(11.5 <= p["time"] <= 14.5 for p in pk)
    assert all(abs(a["time"] - b["time"]) >= 4 for a in pk for b in pk if a is not b)


def test_peaks_need_enough_danmaku():
    assert rx.peaks([(1.0, "a"), (9.0, "b")], duration=30, n=3) == []


def test_load_skips_effects_and_blanks():
    dms = [SimpleNamespace(dm_time=3, text="ok", mode=1), SimpleNamespace(dm_time=1, text="fx", mode=7), SimpleNamespace(dm_time=2, text=" ", mode=1)]
    assert rx.load(dms) == [(3.0, "ok")]


def _sprite() -> bytes:
    img = Image.new("RGB", (20, 20))
    for k, colour in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]):
        img.paste(colour, ((k % 2) * 10, (k // 2) * 10, (k % 2) * 10 + 10, (k // 2) * 10 + 10))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_grab_preview_skips_the_placeholder_and_takes_the_nearest_thumbnail(tmp_path, monkeypatch):
    sprite = _sprite()
    monkeypatch.setattr(fr, "web_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=sprite))))
    snap = {"index": [0, 0, 6, 12, 18], "image": ["//x/sprite.png"], "img_x_len": 2, "img_y_len": 2, "img_x_size": 10, "img_y_size": 10}
    items = asyncio.run(fr.grab_preview(snap, [0, 5, 11, 20], tmp_path))
    assert [i["actual_time"] for i in items] == [0, 6, 12, 18]
    colours = [Image.open(i["path"]).convert("RGB").getpixel((5, 5)) for i in items]
    dominant = [max(range(3), key=lambda ch: c[ch]) if min(c) < 200 else "white" for c in colours]
    assert dominant == [0, 1, 2, "white"]


def test_dedupe_keeps_one_frame_per_thumbnail():
    items = [{"actual_time": 6}, {"actual_time": 6}, {"actual_time": 12}]
    assert fr.dedupe(items) == [{"actual_time": 6}, {"actual_time": 12}]


def test_contact_sheet_puts_reactions_under_the_picture(tmp_path):
    frames = []
    for k in range(2):
        p = tmp_path / f"f{k}.jpg"
        Image.new("RGB", (480, 270), (40 * k, 80, 120)).save(p)
        frames.append({"path": str(p), "actual_time": 3.0 + 10 * k, "danmaku": {"count": 2, "top": [{"text": "一眼万年", "n": 2}]}})
    frames[1]["peak"] = True
    out = fr.contact_sheet(frames, tmp_path / "sheet.jpg", density=[0, 3, 9, 1], duration=20)
    sheet = Image.open(out)
    assert sheet.width == 960 and sheet.height > 270  # caption strip and density bar below the 270 px tiles
    assert sheet.getpixel((240, 135)) == Image.open(frames[0]["path"]).getpixel((240, 135))  # picture itself untouched


def test_danmaku_peaks_command(monkeypatch):
    from typer.testing import CliRunner

    from bili_cli.commands import video as video_cmd
    from bili_cli.main import app

    class FakeVideo:
        async def get_danmakus(self, page_index=0):
            return [SimpleNamespace(dm_time=25 + i / 20, text="一眼万年", mode=1, send_time=0) for i in range(40)] + [
                SimpleNamespace(dm_time=float(t), text="路过", mode=1, send_time=0) for t in range(30)
            ]

        async def get_info(self):
            return {"pages": [{"cid": 1, "duration": 33}]}

    monkeypatch.setattr(video_cmd, "_video", lambda vid: FakeVideo())
    r = CliRunner().invoke(app, ["--compact", "video", "danmaku", "BV1xx411c7mD", "--peaks", "2"])
    data = json.loads(r.stdout)["data"]
    assert data["total"] == 70 and "note" in data
    assert data["peaks"][0]["top"][0] == "一眼万年" and data["peaks"][0]["time_str"].startswith("0:2")
