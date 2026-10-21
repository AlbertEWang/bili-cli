import asyncio

import pytest

from bili_cli import output
from bili_cli.commands import comment as comment_cmd
from bili_cli.commands import owner as owner_cmd
from bili_cli.commands import user as user_cmd
from bili_cli.errors import BiliError


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))
    return tmp_path


def test_at_accepts_nicknames(monkeypatch):
    async def fake_search(keyword, search_type):
        return {"result": [{"uname": "冬冰", "mid": 7}]}

    async def fake_user(mid):
        return {"mid": mid, "name": {7: "冬冰", 42: "Ste_l"}[mid]}

    monkeypatch.setattr(user_cmd.search, "search_by_type", fake_search)
    monkeypatch.setattr(owner_cmd, "resolve_user", fake_user)
    assert asyncio.run(comment_cmd._mentions(["@冬冰", "42"])) == {"冬冰": 7, "Ste_l": 42}
    with pytest.raises(BiliError):
        asyncio.run(comment_cmd._mentions(["1", "2", "3", "4"]))


def test_comment_images_are_checked_before_anything_is_sent(tmp_path, monkeypatch):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    comment_cmd.check_images([img])
    with pytest.raises(BiliError):
        comment_cmd.check_images([tmp_path / "missing.png"])
    with pytest.raises(BiliError):
        comment_cmd.check_images([img] * 10)

    monkeypatch.setattr(comment_cmd.config, "require_credential", lambda: object())
    monkeypatch.setattr(output.settings, "dry_run", True)
    out = asyncio.run(comment_cmd._send("BV1bwnF6eEe8", "video", "看图", None, None, [], [img]))
    assert out["dry_run"] and out["params"]["images"] == [str(img)]
    with pytest.raises(BiliError, match="楼中楼"):  # B 站: "子评论不能带图"
        asyncio.run(comment_cmd._send("BV1bwnF6eEe8", "video", "看图", 123, None, [], [img]))


PACKAGES = [
    {"id": 1, "text": "小黄脸", "emote": [{"text": "[笑哭]", "meta": {"alias": "笑哭"}}, {"text": "[doge]"}] + [{"text": f"[x{i}]"} for i in range(10)]},
    {"id": 2, "text": "tv_小电视", "emote": [{"text": "[tv_doge]"}]},
]


def test_emotes_summary_search_and_package():
    s = comment_cmd.summarize_emotes(PACKAGES, None, None)
    assert s["packages"][0] == {"name": "小黄脸", "count": 12, "sample": ["[笑哭]", "[doge]"] + [f"[x{i}]" for i in range(6)]}
    assert comment_cmd.summarize_emotes(PACKAGES, "DOGE", None)["emotes"] == ["[doge]", "[tv_doge]"]
    assert comment_cmd.summarize_emotes(PACKAGES, None, "tv_小电视")["emotes"] == ["[tv_doge]"]
    with pytest.raises(BiliError):
        comment_cmd.summarize_emotes(PACKAGES, None, "不存在")
