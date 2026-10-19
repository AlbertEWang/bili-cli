import pytest

from bili_cli.commands.upload import build_chapters, parse_chapter_lines, parse_timestamp
from bili_cli.errors import BiliError


@pytest.mark.parametrize("value, seconds", [("90", 90), ("1:30", 90), ("01:30", 90), ("0:01:30", 90), ("1：05", 65)])
def test_parse_timestamp(value, seconds):
    assert parse_timestamp(value) == seconds


@pytest.mark.parametrize("value", ["abc", "1:2:3:4", "-5"])
def test_parse_timestamp_invalid(value):
    with pytest.raises(BiliError):
        parse_timestamp(value)


def test_parse_chapter_lines_skips_blank_and_keeps_spaces_in_title():
    assert parse_chapter_lines(["0:00 开场 介绍", "", "1:30 正片"]) == [(0, "开场 介绍"), (90, "正片")]
    with pytest.raises(BiliError):
        parse_chapter_lines(["1:30"])


def test_build_chapters_fills_end_times_and_sorts():
    cards = build_chapters([(30, "B"), (0, "A")], duration=60, limit=10, min_seconds=5)
    assert cards == [{"from": 0, "to": 30, "content": "A"}, {"from": 30, "to": 60, "content": "B"}]


@pytest.mark.parametrize(
    "items, message",
    [
        ([(10, "A")], "0:00"),
        ([(0, "A"), (2, "B")], "至少 5 秒"),
        ([(0, "A"), (70, "B")], "超出视频时长"),
        ([(i * 6, str(i)) for i in range(11)], "最多 10"),
    ],
)
def test_build_chapters_rejects(items, message):
    with pytest.raises(BiliError) as e:
        build_chapters(items, duration=100 if len(items) > 2 else 60, limit=10, min_seconds=5)
    assert message in e.value.message
