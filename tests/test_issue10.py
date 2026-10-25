import pytest
from bilibili_api import Credential

from bili_cli import config
from bili_cli.commands.me import summarize_stats
from bili_cli.errors import BiliError


def test_me_stats_survives_an_account_with_no_data():
    # the raw payload from issue #10: a new account, 1 fan, 0 plays
    out = summarize_stats(
        None,
        {"follow": 0, "unfollow": 0, "all_fans_acc": 1, "all_fans": 1, "log_date": 20261024},
        {"play_proportion": {"android": 0, "h5": 0}, "audience_proportion": None},
        None,
        {"20261024": None},
    )
    assert out["data_date"] == "20261024"
    assert out["plays"] == {"now": None, "previous": None}
    assert out["fans"]["total"] == 1 and out["plays_from_fans_percent"] is None
    assert out["beats_similar_ups_percent"] == {"play": None, "like": None, "new_fans": None, "replydm": None}
    assert out["top_videos_yesterday"] == [] and out["play_platforms_percent"] == {}


def test_every_part_may_be_null():
    out = summarize_stats(None, None, None, None, None)
    assert out["data_date"] is None and out["fans"]["total"] is None


def test_missing_dedeuserid_is_a_clear_error_not_a_type_error():
    with pytest.raises(BiliError) as e:
        config.my_mid(Credential(sessdata="x", bili_jct="y"))
    assert e.value.code == "auth_expired" and "DedeUserID" in e.value.message
    assert config.my_mid(Credential(sessdata="x", dedeuserid="123")) == 123
