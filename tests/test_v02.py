import pytest

from bili_cli import guard
from bili_cli.commands.dynamic import normalize
from bili_cli.commands.feed import _parse_cursor, _reply_command
from bili_cli.errors import BiliError


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))
    monkeypatch.delenv("BILI_CLI_NO_RATE_LIMIT", raising=False)
    return tmp_path


def test_guard_min_interval(isolated_home):
    guard.check("comment")
    guard.record("comment", {"text": "hi"}, {"rpid": 1})
    with pytest.raises(BiliError) as e:
        guard.check("comment")
    assert e.value.code == "rate_limited"
    assert 0 < e.value.detail["retry_after"] <= guard.LIMITS["comment"][0] + 1
    # other actions have their own budget
    guard.check("like")
    assert (isolated_home / "audit.log").read_text(encoding="utf-8").count('"action": "comment"') == 1


def test_guard_hourly_cap(monkeypatch):
    monkeypatch.setitem(guard.LIMITS, "dynamic", (0, 2))
    for _ in range(2):
        guard.check("dynamic")
        guard.record("dynamic", {}, None)
    with pytest.raises(BiliError) as e:
        guard.check("dynamic")
    assert "1 小时" in e.value.message


def test_guard_can_be_disabled(monkeypatch):
    guard.record("comment", {}, None)
    monkeypatch.setenv("BILI_CLI_NO_RATE_LIMIT", "1")
    guard.check("comment")


def test_reply_command_root_comment_on_video():
    item = {"business_id": 1, "source_id": 111, "root_id": 0, "subject_id": 999, "uri": "https://www.bilibili.com/video/BV1pMYQ6vEua"}
    assert _reply_command(item) == 'bili comment reply BV1pMYQ6vEua 111 "<回复内容>"'


def test_reply_command_nested_on_dynamic():
    item = {"business_id": 17, "source_id": 222, "root_id": 111, "subject_id": 999, "uri": "https://t.bilibili.com/999"}
    assert _reply_command(item) == 'bili comment reply 999 222 --root 111 --type dynamic "<回复内容>"'


def test_reply_command_unknown_business():
    assert _reply_command({"business_id": 42, "source_id": 1}) is None


def test_like_notice_for_comment_and_video():
    from bili_cli.commands.feed import _like

    raw = {
        "id": 1, "counts": 3, "like_time": 200,
        "users": [{"mid": i, "nickname": f"u{i}"} for i in range(5)],
        "item": {"item_id": 99, "type": "reply", "title": "我的评论", "uri": "https://www.bilibili.com/video/BV1xx411c7mD"},
    }
    n = _like(raw, last_view_at=100)
    assert n["is_new"] and n["total_likes"] == 3 and len(n["users"]) == 3
    assert n["liked"] == {"type": "comment", "text": "我的评论", "rpid": 99, "bvid": "BV1xx411c7mD", "url": raw["item"]["uri"]}
    video = _like({**raw, "item": {**raw["item"], "type": "video"}}, last_view_at=300)
    assert video["liked"]["type"] == "video" and video["liked"]["rpid"] is None and not video["is_new"]


def test_system_markup_is_readable():
    from bili_cli.commands.feed import _MARKUP_RE

    text = "恭喜通过。#{点击查看>>}{https://example.com/x}"
    assert _MARKUP_RE.sub(lambda m: f"{m.group(1)}（{m.group(2)}）", text) == "恭喜通过。点击查看>>（https://example.com/x）"


def test_parse_cursor():
    assert _parse_cursor(None) == (None, None)
    assert _parse_cursor("12,34") == (12, 34)
    with pytest.raises(BiliError):
        _parse_cursor("garbage")


def test_normalize_image_dynamic():
    item = {
        "id_str": "100",
        "type": "DYNAMIC_TYPE_DRAW",
        "basic": {"comment_type": 11, "comment_id_str": "555"},
        "modules": {
            "module_author": {"mid": 1, "name": "up", "pub_ts": "1700000000"},
            "module_dynamic": {"major": {"opus": {"summary": {"text": "hello"}, "pics": [{"url": "http://img"}]}}},
            "module_stat": {"comment": {"count": 3}, "like": {"count": 5}, "forward": {"count": 0}},
        },
    }
    out = normalize(item)
    assert out["type"] == "image" and out["text"] == "hello" and out["images"] == ["http://img"]
    assert out["stat"] == {"comment": 3, "like": 5, "forward": 0}
    assert out["comments"]["list_with"] == "bili comment list 555 --type draw"


def test_normalize_video_dynamic_uses_bvid_for_comments():
    item = {
        "id_str": "200",
        "type": "DYNAMIC_TYPE_AV",
        "basic": {"comment_type": 1, "comment_id_str": "80433022"},
        "modules": {"module_dynamic": {"major": {"archive": {"bvid": "BV1GJ411x7h7", "title": "t"}}}},
    }
    out = normalize(item)
    assert out["comments"]["list_with"] == "bili comment list BV1GJ411x7h7"
