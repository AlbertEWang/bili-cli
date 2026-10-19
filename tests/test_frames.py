import pytest

from bili_cli.errors import BiliError
from bili_cli.frames import fmt_time, pick_stream, plan_times


def test_plan_times_default_is_nine_evenly_spaced_centres():
    times = plan_times(90, count=None)
    assert times == [5.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0]


def test_plan_times_every_skips_black_first_frame():
    assert plan_times(40, every=15) == [1.0, 15.0, 30.0]


def test_plan_times_at_and_bounds():
    assert plan_times(100, at=[90, 10]) == [10.0, 90.0]
    with pytest.raises(BiliError):
        plan_times(100, at=[100])


def test_plan_times_chapters():
    assert plan_times(100, chapter_starts=[0, 50]) == [3.0, 53.0]
    with pytest.raises(BiliError) as e:
        plan_times(100, chapter_starts=[])
    assert e.value.code == "not_found"


def test_fmt_time():
    assert fmt_time(65) == "1:05"
    assert fmt_time(3725) == "1:02:05"


def test_pick_stream_prefers_h264_up_to_720p():
    streams = [
        {"codecs": "hev1.1", "height": 720},
        {"codecs": "avc1.640032", "height": 1080},
        {"codecs": "avc1.64001F", "height": 720},
        {"codecs": "avc1.64001E", "height": 480},
    ]
    assert pick_stream({"dash": {"video": streams}}) == streams[2]
    with pytest.raises(BiliError):
        pick_stream({"dash": {"video": []}})
