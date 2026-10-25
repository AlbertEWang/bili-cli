import asyncio
import json
import types

import pytest

from bili_cli import im_push
from bili_cli.commands import dm as dm_cmd
from bili_cli.commands import dm_watch

FUTURE = 10 ** 17   # a session_ts (microseconds) after any test starts


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
        self.params = params
        return self

    def update_data(self, **data):
        FakeApi.calls.append((self.url.rsplit("/", 1)[-1], data))
        return self

    @property
    def result(self):
        async def res():
            name = self.url.rsplit("/", 1)[-1]
            data = FakeApi.responses.get(name, {})
            if name == "new_sessions":   # like the real endpoint: only sessions newer than begin_ts
                since = getattr(self, "params", {}).get("begin_ts", 0)
                data = {"session_list": [x for x in data.get("session_list") or [] if x.get("session_ts", 0) > since]}
            return data
        return res()


def test_watch_reports_only_new_messages_from_the_other_side(monkeypatch):
    FakeApi.calls = []
    FakeApi.responses = {
        "get_sessions": {"session_list": [{"talker_id": 5, "max_seqno": 10, "session_ts": 1}]},
        "new_sessions": {"session_list": [
            {"talker_id": 5, "max_seqno": 13, "session_ts": FUTURE, "session_type": 1, "unread_count": 1, "last_msg": {"sender_uid": 5}},
            # only our follow auto-reply went out: nothing to fetch
            {"talker_id": 6, "max_seqno": 20, "session_ts": FUTURE + 1, "session_type": 1, "unread_count": 0, "last_msg": {"sender_uid": 99}},
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


def _fake_env(monkeypatch, sessions, new_sessions, pages, fail_times=0):
    """Wire _watch to fakes. pages: talker -> list of messages. The first `fail_times` fetches raise a timeout."""
    FakeApi.calls = []
    FakeApi.responses = {"get_sessions": {"session_list": sessions}, "new_sessions": {"session_list": new_sessions}}
    events, state = [], {"fails": fail_times}

    async def fake_page(cred, talker, **params):
        if state["fails"]:
            state["fails"] -= 1
            raise TimeoutError("curl: (28) Operation timed out")
        return {"messages": [m for m in pages.get(talker, []) if m["msg_seqno"] > params.get("begin_seqno", 0)]}

    async def fake_names(mids):
        return {m: f"u{m}" for m in mids}

    monkeypatch.setattr(dm_watch, "Api", FakeApi)
    monkeypatch.setattr(dm_watch, "_page", fake_page)
    monkeypatch.setattr(dm_watch, "_names", fake_names)
    monkeypatch.setattr(dm_watch, "_emit", events.append)
    monkeypatch.setattr(dm_watch, "COALESCE", 0)
    monkeypatch.setattr(dm_watch.config, "require_credential", lambda: types.SimpleNamespace(dedeuserid="99"))
    monkeypatch.setattr(dm_watch.config, "load_owner", lambda: None)
    return events


def _msg(seq, sender, text, ts=4_000_000_000):
    return {"msg_seqno": seq, "sender_uid": sender, "msg_type": 1, "content": json.dumps({"content": text}), "timestamp": ts}


def test_a_failed_fetch_is_retried_not_lost(monkeypatch):
    # the conversation changes once; the first fetch times out. The message must still come out on a later round.
    events = _fake_env(monkeypatch,
                       sessions=[{"talker_id": 5, "max_seqno": 10, "session_ts": 1}],
                       new_sessions=[{"talker_id": 5, "max_seqno": 11, "session_ts": FUTURE, "session_type": 1, "unread_count": 1, "last_msg": {"sender_uid": 5}}],
                       pages={5: [_msg(10, 5, "old"), _msg(11, 5, "在吗")]}, fail_times=1)
    monkeypatch.setattr(dm_watch, "MAX_BACKOFF", 0.05)
    out = asyncio.run(dm_watch._watch(duration=5, max_events=1, only=None, include_self=False, poll=0.02, mark_read=False, no_push=True))
    assert [e["text"] for e in events if e["event"] == "message"] == ["在吗"]
    assert any(e["event"] == "warning" for e in events) and any(e["event"] == "recovered" for e in events)
    assert out["stopped"] == "max_events"


def test_backlog_delivers_unread_from_the_last_read_position(monkeypatch):
    events = _fake_env(monkeypatch,
                       sessions=[{"talker_id": 7, "max_seqno": 23, "ack_seqno": 21, "unread_count": 2, "session_ts": 1, "last_msg": {"sender_uid": 7}},
                                 {"talker_id": 8, "max_seqno": 5, "ack_seqno": 5, "unread_count": 0, "session_ts": 1, "last_msg": {"sender_uid": 99}}],
                       new_sessions=[], pages={7: [_msg(21, 7, "read"), _msg(22, 7, "a", 1), _msg(23, 7, "b", 1)]})
    out = asyncio.run(dm_watch._watch(duration=5, max_events=2, only=None, include_self=False, poll=0.02, mark_read=False, no_push=True, backlog=True))
    assert [e["text"] for e in events if e["event"] == "message"] == ["a", "b"]
    assert out["stopped"] == "max_events"


def test_read_survives_non_object_content():
    assert dm_cmd._content({"msg_type": 10, "content": "12345"}) == "12345"
    assert dm_cmd._content({"msg_type": 1, "content": json.dumps({"content": "hi"})}) == "hi"


def test_watch_always_stops_on_time(monkeypatch):
    # asyncio.wait_for (< 3.12) can swallow the cancellation: the worker then never exits. Run many short watches.
    import time
    _fake_env(monkeypatch, sessions=[{"talker_id": 5, "max_seqno": 10, "session_ts": 1}], new_sessions=[], pages={})
    for _ in range(15):
        t = time.time()
        out = asyncio.run(dm_watch._watch(duration=0.2, max_events=1, only=None, include_self=False, poll=0.005, mark_read=False, no_push=True))
        assert out["stopped"] == "duration" and time.time() - t < 2


def test_dm_send_image_sends_text_then_each_image(monkeypatch, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    sent = []

    async def fake_send_one(cred, me, talker, msg_type, content):
        sent.append((msg_type, json.loads(content)))
        return {"msg_key": len(sent)}

    async def fake_image_content(cred, path):
        return json.dumps({"url": "https://i0.hdslb.com/x.png", "width": 10, "height": 10, "imageType": "png", "original": 1, "size": 0.1})

    async def fake_may(cred, talker):
        return "they_messaged_us"

    monkeypatch.setattr(dm_cmd, "_send_one", fake_send_one)
    monkeypatch.setattr(dm_cmd, "_image_content", fake_image_content)
    monkeypatch.setattr(dm_cmd, "_may_message", fake_may)
    monkeypatch.setattr(dm_cmd.config, "require_credential", lambda: types.SimpleNamespace(dedeuserid="99"))
    from typer.testing import CliRunner
    from bili_cli.main import app
    r = CliRunner().invoke(app, ["--compact", "dm", "send", "123", "看图", "--image", str(img)])
    out = json.loads(r.stdout)
    assert out["ok"] and out["data"]["msg_keys"] == [1, 2], r.stdout
    assert [t for t, _ in sent] == [1, 2] and sent[0][1] == {"content": "看图"} and sent[1][1]["url"].startswith("https://")
    r = CliRunner().invoke(app, ["--compact", "dm", "send", "123"])
    assert json.loads(r.stdout)["error"]["code"] == "invalid_argument"
