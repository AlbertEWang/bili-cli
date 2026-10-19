import json
from pathlib import Path

import pytest

from bili_cli.commands import mcp as mcp_cmd


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    return tmp_path


def test_json_merge_keeps_other_settings_and_backs_up(fake_home):
    cfg = fake_home / ".gemini" / "settings.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    step = mcp_cmd._plan("gemini", remove=False)
    assert step["available"] and step["path"] == str(cfg)
    mcp_cmd._apply(step, remove=False)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and "other" in data["mcpServers"]
    assert data["mcpServers"]["bili-cli"]["args"][-2:] == ["mcp", "serve"]
    assert cfg.with_suffix(".json.bak").exists()
    mcp_cmd._apply(mcp_cmd._plan("gemini", remove=True), remove=True)
    assert set(json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]) == {"other"}


def test_vscode_uses_servers_key_with_stdio_type(fake_home):
    step = mcp_cmd._plan("vscode", remove=False)
    mcp_cmd._apply(step, remove=False)
    data = json.loads(Path(step["path"]).read_text(encoding="utf-8"))
    assert data["servers"]["bili-cli"]["type"] == "stdio"


def test_invalid_json_is_left_alone(fake_home):
    cfg = fake_home / ".cursor" / "mcp.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("{not json", encoding="utf-8")
    with pytest.raises(Exception):
        mcp_cmd._apply(mcp_cmd._plan("cursor", remove=False), remove=False)
    assert cfg.read_text(encoding="utf-8") == "{not json"


def test_cli_clients_use_official_commands():
    argv = mcp_cmd._plan("claude-code", remove=False)["argv"]
    assert argv[:5] == ["claude", "mcp", "add", "-s", "user"] and argv[-2:] == ["mcp", "serve"]
    assert mcp_cmd._plan("codex", remove=True)["argv"] == ["codex", "mcp", "remove", "bili-cli"]


def test_server_registers_curated_tools_with_annotations():
    pytest.importorskip("mcp")
    import asyncio

    from bili_cli.mcp_server import build_server

    async def tools():
        server = build_server()
        return {t.name: t for t in await server.list_tools()}

    found = asyncio.run(tools())
    assert {"inbox", "watch_video", "post_comment", "send_dm", "run_bili"} <= set(found)
    assert found["inbox"].annotations.read_only_hint is True
    assert found["send_dm"].annotations.read_only_hint is False


def test_run_bili_refuses_local_config_commands():
    pytest.importorskip("mcp")
    import asyncio

    from bili_cli.mcp_server import build_server

    async def call():
        return await build_server().call_tool("run_bili", {"args": ["skills", "install", "--yes"]})

    result = asyncio.run(call())
    assert "修改本机配置" in json.dumps(result, ensure_ascii=False, default=str)
