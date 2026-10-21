import asyncio
import json

import pytest

from bili_cli import cards, config
from bili_cli.commands import comment as comment_cmd
from bili_cli.commands.dm import _content, _resolve_uid
from bili_cli.errors import BiliError


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))
    return tmp_path


def test_video_card_normalises_reason_and_desc():
    item = {
        "bvid": "BV1x", "title": "t", "owner": {"mid": 1, "name": "up", "face": "x"}, "duration": 60, "pubdate": 1700000000,
        "stat": {"view": 10, "like": 2, "danmaku": 1, "reply": 0, "vt": 0}, "rcmd_reason": {"content": "百万播放"}, "desc": "长" * 100,
    }
    card = cards.video_card(item)
    assert card["reason"] == "百万播放" and card["author"] == {"mid": 1, "name": "up"}
    assert card["stat"] == {"view": 10, "like": 2, "danmaku": 1, "reply": 0}
    assert len(card["desc"]) == cards.DESC_MAX + 1
    assert cards.video_card({**item, "rcmd_reason": "最豪幻想", "desc": "-"}).get("desc") is None
    assert cards.video_card({**item, "rcmd_reason": "最豪幻想"})["reason"] == "最豪幻想"


def test_seen_list_filters():
    items = [{"bvid": "BV1"}, {"bvid": "BV2"}]
    cards.mark_seen("BV1")
    assert cards.filter_unseen(items, True) == [{"bvid": "BV2"}]
    assert cards.filter_unseen(items, False) == items


def test_dm_content_decoding():
    assert _content({"msg_type": 1, "content": json.dumps({"content": "你好"})}) == "你好"
    assert _content({"msg_type": 2, "content": json.dumps({"url": "http://img"})}) == "[图片] http://img"
    assert _content({"msg_type": 7, "content": json.dumps({"title": "视频", "bvid": "BV1"})}) == "[分享视频] 视频 BV1"
    assert _content({"msg_type": 1, "content": "not json"}) == "not json"


def test_owner_resolution_requires_setup():
    with pytest.raises(BiliError):
        _resolve_uid("owner")
    config.save_owner({"mid": 42, "name": "主人"})
    assert _resolve_uid("owner") == 42 and _resolve_uid("7") == 7
    with pytest.raises(BiliError):
        _resolve_uid("someone")


def test_mentions_resolve_owner_and_limit(monkeypatch):
    async def fake_resolve(mid):
        return {"mid": mid, "name": f"user{mid}"}

    monkeypatch.setattr("bili_cli.commands.owner.resolve_user", fake_resolve)
    config.save_owner({"mid": 42, "name": "old name"})
    assert asyncio.run(comment_cmd._mentions(["owner", "7"])) == {"user42": 42, "user7": 7}
    with pytest.raises(BiliError):
        asyncio.run(comment_cmd._mentions(["1", "2", "3", "4"]))


def test_device_id_is_stable():
    first = config.device_id()
    assert first == config.device_id() and len(first) == 36
