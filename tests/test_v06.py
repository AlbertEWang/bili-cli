import pytest

from bili_cli.commands import autoreply as ar
from bili_cli.commands import dynamic as dyn
from bili_cli.commands import season as season_cmd
from bili_cli.errors import BiliError


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("BILI_CLI_HOME", str(tmp_path))


def test_vote_validation_and_payload():
    dyn.check_vote(None, [], 1, 7)  # no vote at all
    dyn.check_vote("下期做什么", ["A", "B"], 2, 30)
    for args in [(None, ["A"], 1, 7), ("t", ["A"], 1, 7), ("t", ["A", "B"], 3, 7), ("t", ["A", "B"], 1, 31)]:
        with pytest.raises(BiliError):
            dyn.check_vote(*args)
    body = dyn.vote_payload("下期做什么", ["A", "B"], 1, 3, 42)["vote_info"]
    assert body["duration"] == 3 * 86400 and body["vote_publisher"] == 42
    assert body["options"] == [{"opt_desc": "A", "img_url": ""}, {"opt_desc": "B", "img_url": ""}]


def test_vote_card_on_a_dynamic():
    mod = {"additional": {"type": "ADDITIONAL_TYPE_VOTE", "vote": {"vote_id": 9, "title": "测试投票", "desc": "0人参与", "join_num": None, "end_time": 0}}}
    card = dyn._vote_card(mod)
    assert card["title"] == "测试投票" and card["joined"] == 0 and card["results_with"] == "bili dynamic vote 9"
    assert dyn._vote_card({}) is None


def test_season_summary():
    entry = {
        "season": {"id": 1, "title": "自制游戏", "state": -6, "ep_count": 0, "mtime": 0},
        "sections": {"sections": [{"id": 11, "title": "正片"}]},
        "part_episodes": [{"bvid": "BV1", "title": "第一集"}],
    }
    s = season_cmd.summarize_season(entry)
    assert s["state"] == "审核中" and s["videos"] == 1 and s["sections"] == [{"id": 11, "title": "正片"}]


def test_autoreply_summary_and_rules():
    settings = {"followed_reply": 1, "recv_reply": 0, "voyage_reply": 1, "keys_reply": 1}
    texts = {"follow": [{"reply": "感谢关注"}], "keyword": [{"id": 5, "title": "拜师", "key1": "师傅", "key2": "拜师，收徒", "reply": "嗯"}]}
    s = ar.summarize(settings, texts)
    assert s["follow"] == {"on": True, "reply": "感谢关注"} and s["message"] == {"on": False, "reply": None}
    assert s["keyword"]["rules"][0] == {"id": 5, "name": "拜师", "exact": ["师傅"], "fuzzy": ["拜师", "收徒"], "reply": "嗯"}
    rule = ar.build_rule("教程", ["教程"], ["怎么装", "安装"], "教程在这里")
    assert rule["key2"] == "怎么装，安装" and rule["type"] == 2 and rule["id"] == 0  # full-width comma, 0 = new
    with pytest.raises(BiliError):
        ar.build_rule("空", [], [], "x")
    with pytest.raises(BiliError):
        ar.build_rule("长", ["a"], [], "x" * 501)


def test_global_wait_does_not_swallow_auth_status_wait_seconds():
    from bili_cli.main import _hoist_global_flags
    assert _hoist_global_flags(["auth", "status", "--wait", "120"]) == ["auth", "status", "--wait", "120"]
    assert _hoist_global_flags(["comment", "post", "BV1", "hi", "--wait"]) == ["--wait", "comment", "post", "BV1", "hi"]


def test_iso_time_accepts_numeric_strings():
    from bili_cli.runtime import iso_time

    assert iso_time("1792902428") == iso_time(1792902428)
    assert iso_time("0") is None and iso_time("") is None and iso_time(None) is None


def test_parse_staff():
    from bili_cli.commands.upload import parse_staff

    assert parse_staff(["策划:94782782", "演唱：owner"]) == [("策划", "94782782"), ("演唱", "owner")]
    with pytest.raises(BiliError):
        parse_staff(["94782782"])


def test_check_staff(monkeypatch):
    import asyncio
    import contextlib

    import httpx

    from bili_cli.commands import comment, upload

    pre = {"data": {
        "myinfo": {"mid": 1, "staff_qualification_v2": {"staff_auth": True, "cnt": False}},
        "staff_conf": {"typelist": [{"typeid": 193, "max_staff": 10, "titles": ["策划", "演唱"]}]},
    }}

    @contextlib.asynccontextmanager
    async def fake_client(cred, referer=None):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=pre))) as c:
            yield c

    async def fake_mentions(values, limit):
        return {f"user{v}": int(v) for v in values}

    monkeypatch.setattr(upload, "web_client", fake_client)
    monkeypatch.setattr(comment, "_mentions", fake_mentions)
    check = lambda staff, tid=193: asyncio.run(upload._check_staff(None, tid, staff))
    assert check([("策划", "94782782")]) == [{"title": "策划", "mid": 94782782, "name": "user94782782"}]
    for bad in ([("剪辑", "2")], [("策划", "1")]):
        with pytest.raises(BiliError):
            check(bad)
    with pytest.raises(BiliError):
        check([("策划", "2")], tid=21)
    pre["data"]["myinfo"]["staff_qualification_v2"]["staff_auth"] = False
    with pytest.raises(BiliError):
        check([("策划", "2")])


def test_check_reserve():
    from bili_cli.commands.upload import _check_reserve

    _check_reserve({"act_reserve": {"act_reserve_open": True}})
    for pre in ({}, {"act_reserve": {"act_reserve_open": False}}):
        with pytest.raises(BiliError):
            _check_reserve(pre)
