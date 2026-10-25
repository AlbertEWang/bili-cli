import asyncio
import time
from types import SimpleNamespace

import pytest

from bili_cli import health
from bili_cli.errors import BiliError


@pytest.fixture(autouse=True)
def clean_stats():
    health.stats.take()
    yield
    health.stats.take()


def test_a_frozen_process_is_named_on_the_network_error():
    health.record_tick(100.0, 161.0)  # the heartbeat slept 61 s instead of 1
    err = health.enrich(BiliError("network_error", "Timeout"))
    assert err.detail["stalled_seconds"] == 60
    assert "整个进程停了约 60 秒" in err.hint


def test_a_blocked_loop_is_named_when_the_process_kept_running():
    health.stats.loop_late = 33.0
    err = health.enrich(BiliError("network_error", "Timeout"))
    assert err.detail == {"loop_blocked_seconds": 33} and "事件循环被卡住约 33 秒" in err.hint


def test_ordinary_jitter_and_other_errors_are_left_alone():
    health.record_tick(0.0, 3.5)  # 2.5 s late: noise
    assert health.enrich(BiliError("network_error", "x")).detail == {}
    health.record_tick(0.0, 60.0)
    assert "stalled_seconds" not in health.enrich(BiliError("not_found", "x")).detail


def test_request_guard_cuts_off_hung_reads_but_not_writes(monkeypatch):
    from bilibili_api.utils import network

    async def slow(self, raw=False, byte=False):
        await asyncio.sleep(self.takes)
        return "ok"

    monkeypatch.setattr(network.Api, "_request", slow)
    monkeypatch.setattr(health, "_installed", False)
    monkeypatch.setattr(health, "REQUEST_DEADLINE", 0.2)
    health.install_request_guard()
    guarded = network.Api._request

    get = SimpleNamespace(method="GET", url="https://api.bilibili.com/x", takes=5)
    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(guarded(get))
    assert time.monotonic() - t0 < 2

    post = SimpleNamespace(method="POST", url="https://api.bilibili.com/x", takes=0.4)
    assert asyncio.run(guarded(post)) == "ok"  # a write is never cut off halfway
    assert asyncio.run(guarded(SimpleNamespace(method="GET", url="u", takes=0))) == "ok"
