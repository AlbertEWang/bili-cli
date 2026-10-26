import asyncio
import json
import time

import pytest
from bilibili_api import Credential
from bilibili_api.exceptions import CookiesRefreshException
from bilibili_api.utils import network
from typer.testing import CliRunner

from bili_cli import config
from bili_cli.commands import auth
from bili_cli.main import app


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))
    return tmp_path


def _cookie_info(reply):
    class FakeApi:
        def __init__(self, url, method, credential=None, **kwargs):
            assert url == auth.COOKIE_INFO_URL

        @property
        def result(self):
            async def _result():
                return reply

            return _result()

    return FakeApi


def test_refresh_is_stamped_with_bilibili_time_not_ours(monkeypatch):
    # this PC's clock ran 5 s fast, and Bilibili answers 404 to a correspondPath stamped in its future
    server_ms = round(time.time() * 1000) - 5000
    monkeypatch.setattr(auth, "Api", _cookie_info({"refresh": True, "timestamp": server_ms}))
    monkeypatch.setattr(auth, "_correspond_path", lambda ts: f"path-{ts}")
    original = network._getCorrespondPath
    seen = []

    async def fake_refresh(self):
        seen.append(network._getCorrespondPath())

    monkeypatch.setattr(Credential, "refresh", fake_refresh)
    assert asyncio.run(auth._refresh_cookies(Credential(sessdata="s", bili_jct="j", ac_time_value="r"))) is True
    stamped = int(seen[0].removeprefix("path-"))
    assert server_ms <= stamped < server_ms + 2000
    assert network._getCorrespondPath is original


def test_no_refresh_when_bilibili_does_not_ask(monkeypatch):
    monkeypatch.setattr(auth, "Api", _cookie_info({"refresh": False, "timestamp": 1}))

    async def fail(self):
        raise AssertionError("must not refresh")

    monkeypatch.setattr(Credential, "refresh", fail)
    assert asyncio.run(auth._refresh_cookies(Credential(sessdata="s", bili_jct="j", ac_time_value="r"))) is False


def test_bilibili_api_still_builds_correspond_path_where_we_patch_it():
    assert "_getCorrespondPath" in network._get_refresh_csrf.__code__.co_names
    assert len(auth._correspond_path(1792944000000)) == 256  # RSA-1024 → 128 bytes, hex


def _status(monkeypatch, refresh):
    async def valid(self):
        return True

    async def me(cred):
        return {"mid": 1, "name": "n", "level": 6}

    monkeypatch.setattr(Credential, "check_valid", valid)
    monkeypatch.setattr(auth, "_refresh_cookies", refresh)
    monkeypatch.setattr(auth, "_self_info", me)
    result = CliRunner().invoke(app, ["auth", "status"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["data"]


def test_status_saves_refreshed_cookies(monkeypatch):
    config.save_credential(Credential(sessdata="old", bili_jct="j", dedeuserid="1", ac_time_value="r"))

    async def refresh(cred):
        cred.sessdata = "new"
        return True

    out = _status(monkeypatch, refresh)
    assert out["refreshed"] is True and "refresh_error" not in out
    assert config.load_credential().sessdata == "new"


def test_failed_refresh_keeps_a_valid_login_and_is_not_called_a_bug(monkeypatch):
    config.save_credential(Credential(sessdata="old", bili_jct="j", dedeuserid="1", ac_time_value="r"))

    async def refresh(cred):
        raise CookiesRefreshException("correspondPath 过期或错误。")

    out = _status(monkeypatch, refresh)
    assert out["logged_in"] is True and out["refreshed"] is False
    assert "correspondPath" in out["refresh_error"] and "bili auth login" in out["hint"]
    assert config.load_credential().sessdata == "old"
