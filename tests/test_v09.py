import asyncio
import types

import pytest

from bili_cli.commands import user as user_cmd
from bili_cli.errors import BiliError


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))


class FakeUser:
    calls: list = []

    def __init__(self, mid, credential=None):
        self.mid = mid
        self.attr = 2 if mid == 1 else 0

    async def get_relation(self):
        return {"relation": {"attribute": self.attr}, "be_relation": {"attribute": 0}}

    async def modify_relation(self, relation):
        FakeUser.calls.append((self.mid, relation))
        self.attr = 2 if relation == user_cmd.user.RelationType.SUBSCRIBE else 0


@pytest.fixture
def fake(monkeypatch):
    FakeUser.calls = []
    monkeypatch.setattr(user_cmd.user, "User", FakeUser)
    monkeypatch.setattr(user_cmd.config, "require_credential", lambda: types.SimpleNamespace(dedeuserid="99"))
    return FakeUser


def test_follow_changes_and_reports_relation(fake):
    out = asyncio.run(user_cmd._set_follow("2", True))
    assert out["changed"] and out["i_follow"] and out["relation"] == "following"
    assert fake.calls == [(2, user_cmd.user.RelationType.SUBSCRIBE)]


def test_follow_is_a_noop_when_already_in_that_state(fake):
    assert asyncio.run(user_cmd._set_follow("1", True))["changed"] is False
    assert asyncio.run(user_cmd._set_follow("2", False))["changed"] is False
    assert fake.calls == []


def test_cannot_follow_yourself(fake):
    with pytest.raises(BiliError):
        asyncio.run(user_cmd._set_follow("99", True))


def test_comment_cap_and_curl_timeouts_are_mapped():
    from bilibili_api.exceptions import ResponseCodeException
    from curl_cffi.requests.exceptions import Timeout

    from bili_cli.errors import from_exception

    e = from_exception(ResponseCodeException(12014, "发送失败，已达到当前评论发送上限"))
    assert e.code == "rate_limited" and "1 小时" in e.hint
    assert from_exception(ResponseCodeException(12006, "没有该评论")).code == "not_found"
    assert from_exception(Timeout("curl: (28) Operation timed out")).code == "network_error"
