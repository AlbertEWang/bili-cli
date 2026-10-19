"""Execution guardrails for write operations: local rate limits and an audit log.

Each `bili` invocation is a separate process, so the history lives in the
config dir. Limits are deliberately conservative: an agent that hits one gets
`rate_limited` with `retry_after` and should wait rather than retry blindly.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from . import config
from .errors import BiliError

# action -> (minimum seconds between two actions, maximum actions per hour)
LIMITS: dict[str, tuple[int, int]] = {
    "comment": (10, 30),
    "danmaku": (10, 30),
    "like": (3, 120),
    "delete": (3, 60),
    "dynamic": (60, 10),
    "profile": (30, 10),
    "upload": (300, 5),
    # B 站 throttles interactive components harder than plain danmaku (36703 within a minute).
    "interact": (30, 20),
    "dm": (10, 20),
}
WINDOW_SECONDS = 3600


def _state_path():
    return config.home() / "ratelimit.json"


def _load() -> dict[str, list[float]]:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _disabled() -> bool:
    return os.environ.get("BILI_CLI_NO_RATE_LIMIT") == "1"


def check(action: str) -> None:
    """Raise rate_limited if `action` would exceed its local limit."""
    if _disabled():
        return
    min_interval, per_hour = LIMITS[action]
    now = time.time()
    history = [t for t in _load().get(action, []) if now - t < WINDOW_SECONDS]
    if history and now - history[-1] < min_interval:
        wait = int(min_interval - (now - history[-1])) + 1
        raise BiliError(
            "rate_limited",
            f"{action} 操作间隔至少 {min_interval} 秒。",
            hint=f"等待 {wait} 秒后重试。",
            detail={"action": action, "retry_after": wait, "limit": {"min_interval": min_interval, "per_hour": per_hour}},
        )
    if len(history) >= per_hour:
        wait = int(WINDOW_SECONDS - (now - history[0])) + 1
        raise BiliError(
            "rate_limited",
            f"{action} 操作 1 小时内最多 {per_hour} 次。",
            hint=f"等待 {wait} 秒后重试。",
            detail={"action": action, "retry_after": wait, "limit": {"min_interval": min_interval, "per_hour": per_hour}},
        )


def record(action: str, params: dict[str, Any], result: Any) -> None:
    """Remember a successful write for rate limiting and append it to the audit log."""
    now = time.time()
    state = _load()
    state[action] = [t for t in state.get(action, []) if now - t < WINDOW_SECONDS] + [now]
    tmp = _state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, _state_path())

    entry = {"time": now, "action": action, "params": params, "result": result}
    with open(config.home() / "audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
