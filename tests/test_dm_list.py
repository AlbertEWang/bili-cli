import json

import pytest
from typer.testing import CliRunner

from bili_cli import config
from bili_cli.commands import dm
from bili_cli.main import app


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))


ME = 100


def _session(talker, ts, sender, source=2):
    return {"talker_id": talker, "session_ts": ts, "unread_count": 1,
            "last_msg": {"sender_uid": sender, "msg_type": 1, "content": json.dumps({"content": f"hi {talker}"}),
                         "timestamp": 1793010000, "msg_source": source}}


def _fake_api(pages, calls):
    class FakeApi:
        def __init__(self, url, method="GET", credential=None, **kw):
            self.url = url

        def update_params(self, **params):
            self.params = params
            return self

        @property
        def result(self):
            async def res():
                if self.url.endswith("get_sessions"):
                    calls.append(self.params.get("end_ts"))
                    return pages[self.params.get("end_ts")]
                return [{"mid": int(u), "name": f"u{u}"} for u in self.params["uids"].split(",")]   # user cards
            return res()

    return FakeApi


def _invoke(monkeypatch, pages, argv):
    calls = []
    monkeypatch.setattr(dm, "Api", _fake_api(pages, calls))
    config.save_credential(config.Credential(sessdata="s", bili_jct="j", dedeuserid=str(ME)))
    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["data"]["items"], calls


def test_list_pages_past_the_first_20_sessions(monkeypatch):
    # the endpoint gives 20 per page; --limit 50 used to come back with 20
    first = [_session(i, 1000 - i, i) for i in range(20)]
    second = [_session(i, 1000 - i, i) for i in range(20, 40)]
    pages = {None: {"session_list": first, "has_more": 1}, 981: {"session_list": second, "has_more": 0}}
    items, calls = _invoke(monkeypatch, pages, ["dm", "list", "--limit", "50"])
    assert len(items) == 40 and calls == [None, 981]
    assert items[25]["uid"] == 25 and items[25]["name"] == "u25"


def test_bilibili_auto_reply_is_flagged(monkeypatch):
    # they wrote and followed at once; B 站's follow auto-reply then became the last message
    pages = {None: {"session_list": [_session(7, 5, ME, source=dm.AUTO_REPLY_SOURCE), _session(8, 4, ME, source=4)], "has_more": 0}}
    items, _ = _invoke(monkeypatch, pages, ["dm", "list"])
    assert items[0]["last_message"]["from"] == "me" and items[0]["last_message"]["auto_reply"] is True
    assert "auto_reply" not in items[1]["last_message"]
