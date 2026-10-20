from bili_cli import guard
from bili_cli.commands import comment as comment_cmd


def test_pinned_collects_both_api_shapes_without_duplicates():
    lazy = {"top_replies": [{"rpid": 1}], "upper": {"top": {"rpid": 1}}}
    assert [r["rpid"] for r in comment_cmd._pinned(lazy)] == [1]
    paged = {"upper": {"top": {"rpid": 2}}, "replies": [{"rpid": 3}]}
    assert [r["rpid"] for r in comment_cmd._pinned(paged)] == [2]
    assert comment_cmd._pinned({"replies": [{"rpid": 3}]}) == []


def test_check_finds_pinned_comment():
    # a pinned comment is missing from `replies`, so check used to report it as not found
    out = comment_cmd._check_result(7, [{"rpid": 7, "state": 0}, {"rpid": 8, "state": 0}], {7})
    assert out["found"] and out["visible"] and out["pinned"]
    assert "pinned" not in comment_cmd._check_result(8, [{"rpid": 8, "state": 0}], {7})


def test_check_reports_folded_and_missing():
    folded = comment_cmd._check_result(5, [{"rpid": 5, "state": 0, "folder": {"is_folded": True}}], set())
    assert folded["found"] and not folded["visible"] and folded["folded"]
    assert comment_cmd._check_result(9, [{"rpid": 5}], set())["found"] is False


def test_pin_is_rate_limited():
    assert "pin" in guard.LIMITS
