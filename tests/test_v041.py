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


def test_desc_v2_marks_mentions_in_place_and_prepends_missing_ones():
    from bili_cli.commands import upload as upload_cmd

    text, v2 = upload_cmd.build_desc_v2("角色设计 @冬冰 欢迎关注", {"冬冰": 7, "Ste_l": 42})
    assert text == "@Ste_l 角色设计 @冬冰 欢迎关注"  # the space after a mention belongs to it
    # what B 站 checks (21010 otherwise): desc == desc_v2 with each mention rendered as "@name "
    assert "".join(s["raw_text"] if s["type"] == 1 else f"@{s['raw_text']} " for s in v2) == text
    assert [(s["raw_text"], s["biz_id"]) for s in v2 if s["type"] == 2] == [("Ste_l", "42"), ("冬冰", "7")]
    # the accepted live shape: "角色 " / 一支小馋猫 / " 欢迎关注" <-> "角色 @一支小馋猫  欢迎关注"
    assert upload_cmd.build_desc_v2("角色 @一支小馋猫  欢迎关注", {"一支小馋猫": 1})[1][2]["raw_text"] == " 欢迎关注"
    assert upload_cmd.build_desc_v2("纯文字", {}) == ("纯文字", None)


def test_edit_keeps_existing_desc_mentions_unless_the_text_changes():
    from bili_cli.commands import upload as upload_cmd
    from tests.test_v04 import VIEW

    v2 = [{"raw_text": "@冬冰", "type": 2, "biz_id": "7"}]
    view = {**VIEW, "archive": {**VIEW["archive"], "desc": "@冬冰", "desc_v2": v2}}
    assert upload_cmd.build_edit(view, {"title": "new"})["desc_v2"] == v2
    assert upload_cmd.build_edit(view, {"desc": "新简介"})["desc_v2"] is None


def test_comment_cards_carry_https_image_urls(tmp_path):
    r = {"rpid": 1, "content": {"message": "看图", "pictures": [{"img_src": "http://i0.hdslb.com/bfs/new_dyn/a.jpg"}]}}
    assert comment_cmd._reply(r)["images"] == ["https://i0.hdslb.com/bfs/new_dyn/a.jpg"]
    assert "images" not in comment_cmd._reply({"rpid": 2, "content": {"message": "纯文字"}})
    p = comment_cmd.image_path("https://i0.hdslb.com/bfs/new_dyn/a.jpg", tmp_path)
    assert p.parent == tmp_path and p.suffix == ".jpg"


def test_comment_images_only_fetches_from_bilibili_image_hosts():
    from typer.testing import CliRunner

    from bili_cli.main import app

    res = CliRunner().invoke(app, ["comment", "images", "https://example.com/a.jpg"])
    assert res.exit_code != 0 and "hdslb.com" in res.output
