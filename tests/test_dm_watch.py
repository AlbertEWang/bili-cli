import asyncio
import json
import types

import pytest

from bili_cli import im_push
from bili_cli.commands import dm as dm_cmd
from bili_cli.commands import dm_watch


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))


def test_auth_and_subscribe_frames_round_trip():
    f = im_push.decode_frame(im_push.auth_frame(1, "guid-1"))
    assert (f.path, f.type_name) == (im_push.AUTH, "bilibili.broadcast.v1.AuthReq")
    assert im_push.parse(f.value)[1] == [b"guid-1"]
    f = im_push.decode_frame(im_push.subscribe_frame(2))
    assert f.path == im_push.SUBSCRIBE
    assert im_push.parse(f.value)[1] == [im_push.WATCH_NOTIFY.encode()]


def _notify_frame(payload: bytes) -> bytes:
    rsp = im_push._field_int(1, 99) + im_push._field_int(2, 1) + im_push._field_len(3, payload)
    return im_push.frame(7, im_push.WATCH_NOTIFY, "bilibili.broadcast.message.im.NotifyRsp", rsp)


def test_notify_tells_a_changed_conversation_from_a_badge_update():
    session = im_push._field_len(3, im_push._field_int(1, 1) + im_push._field_int(2, 12345) + im_push._field_int(3, 1))
    f = im_push.decode_frame(_notify_frame(session))
    n = im_push.decode_notify(f.value)
    assert (n.kind, n.talker, n.session_type) == ("session", 12345, 1)

    badge = im_push._field_len(2, im_push._field_int(5, 115) + im_push._field_len(6, b'{"sender_id":7,"msg_key":0}'))
    n = im_push.decode_notify(im_push.decode_frame(_notify_frame(badge)).value)
    assert n.kind == "notice" and n.notice == {"sender_id": 7, "msg_key": 0, "code": 115}


def test_history_pages_backwards_and_stops_when_the_endpoint_does_not_page(monkeypatch):
    pages = {None: list(range(71, 101)), 71: list(range(41, 71)), 41: list(range(41, 71))}   # third call repeats: stop

    async def fake_page(cred, talker, **params):
        seqs = pages[params.get("end_seqno")]
        return {"messages": [{"msg_seqno": s} for s in seqs], "has_more": 1}

    monkeypatch.setattr(dm_cmd, "_page", fake_page)
    msgs = asyncio.run(dm_cmd._history(None, 5, 100))
    assert [m["msg_seqno"] for m in msgs] == list(range(41, 101))


class FakeApi:
    responses: dict = {}
    calls: list = []

    def __init__(self, url, method="GET", credential=None, **kw):
        self.url = url

    def update_params(self, **params):
        FakeApi.calls.append((self.url.rsplit("/", 1)[-1], params))
        return self

    def update_data(self, **data):
        FakeApi.calls.append((self.url.rsplit("/", 1)[-1], data))
        return self

    @property
    def result(self):
        async def res():
            return FakeApi.responses.get(self.url.rsplit("/", 1)[-1], {})
        return res()


def test_watch_reports_only_new_messages_from_the_other_side(monkeypatch):
    FakeApi.calls = []
    FakeApi.responses = {
        "get_sessions": {"session_list": [{"talker_id": 5, "max_seqno": 10, "session_ts": 1}]},
        "new_sessions": {"session_list": [
            {"talker_id": 5, "max_seqno": 13, "session_ts": 2, "session_type": 1, "unread_count": 1, "last_msg": {"sender_uid": 5}},
            # only our follow auto-reply went out: nothing to fetch
            {"talker_id": 6, "max_seqno": 20, "session_ts": 3, "session_type": 1, "unread_count": 0, "last_msg": {"sender_uid": 99}},
        ]},
    }
    fetched = []
    events = []
    msgs = [
        {"msg_seqno": 10, "sender_uid": 5, "msg_type": 1, "content": json.dumps({"content": "old"}), "timestamp": 1},
        {"msg_seqno": 12, "sender_uid": 99, "msg_type": 1, "content": json.dumps({"content": "mine"}), "timestamp": 2, "msg_source": 8},
        {"msg_seqno": 13, "sender_uid": 5, "msg_type": 1, "content": json.dumps({"content": "hi"}), "timestamp": 3},
    ]

    async def fake_page(cred, talker, **params):
        fetched.append(talker)
        return {"messages": [m for m in msgs if m["msg_seqno"] > params.get("begin_seqno", 0)]}

    async def fake_names(mids):
        return {5: "fan"}

    monkeypatch.setattr(dm_watch, "Api", FakeApi)
    monkeypatch.setattr(dm_watch, "_page", fake_page)
    monkeypatch.setattr(dm_watch, "_names", fake_names)
    monkeypatch.setattr(dm_watch, "_emit", events.append)
    monkeypatch.setattr(dm_watch, "COALESCE", 0)
    monkeypatch.setattr(dm_watch.config, "require_credential", lambda: types.SimpleNamespace(dedeuserid="99"))
    monkeypatch.setattr(dm_watch.config, "load_owner", lambda: None)

    out = asyncio.run(dm_watch._watch(duration=5, max_events=1, only=None, include_self=False, poll=0.05, mark_read=False, no_push=True))
    got = [e for e in events if e["event"] == "message"]
    assert [(e["uid"], e["from"], e["text"], e["name"]) for e in got] == [(5, "them", "hi", "fan")]
    assert out["stopped"] == "max_events" and out["messages"] == 1
    assert fetched == [5]
