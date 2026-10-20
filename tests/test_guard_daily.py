import json
import time

import pytest

from bili_cli import guard
from bili_cli.errors import BiliError


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))
    monkeypatch.delenv("BILI_CLI_NO_RATE_LIMIT", raising=False)
    monkeypatch.setitem(guard.LIMITS, "coin", (0, 100))  # isolate the daily cap from the hourly one
    return tmp_path


def test_coins_count_units_against_daily_cap():
    guard.check("coin", units=2)
    guard.record("coin", {"bvid": "BV1"}, "ok", units=2)
    guard.check("coin", units=2)
    guard.record("coin", {"bvid": "BV2"}, "ok", units=2)
    with pytest.raises(BiliError) as e:
        guard.check("coin", units=2)  # 4 used + 2 > 5
    assert e.value.code == "rate_limited" and e.value.detail["limit"] == {"per_day": 5, "used": 4}
    guard.check("coin", units=1)  # exactly reaching 5 is fine


def test_daily_history_survives_the_hourly_window(isolated_home):
    state = {"coin": [time.time() - 2 * 3600] * 5}  # 5 coins two hours ago
    (isolated_home / "ratelimit.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(BiliError):
        guard.check("coin", units=1)
    guard.record("comment", {}, None)  # recording another action must not prune coin history
    assert len(json.loads((isolated_home / "ratelimit.json").read_text())["coin"]) == 5


def test_old_coins_expire_after_a_day(isolated_home):
    state = {"coin": [time.time() - 25 * 3600] * 5}
    (isolated_home / "ratelimit.json").write_text(json.dumps(state), encoding="utf-8")
    guard.check("coin", units=2)
