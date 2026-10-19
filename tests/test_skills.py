import json
from pathlib import Path

import pytest

from bili_cli import skills as sk


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for var in ("CLAUDE_CONFIG_DIR", "OPENCLAW_HOME", "CODEX_HOME", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(var, raising=False)
    # guard: every target must resolve inside the temp home, never the real one
    assert all(str(t.skill_dir()).startswith(str(tmp_path)) for t in sk.TARGETS)
    return tmp_path


def by_agent(rows):
    return {r["agent"]: r for r in rows}


def test_bundled_skill_is_valid_agent_skill():
    src = sk.bundled_dir()
    text = (src / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front = text.split("---\n")[1]
    assert f"name: {sk.SKILL_NAME}\n" in front and src.name == sk.SKILL_NAME  # spec: name must match folder
    description = next(line for line in front.splitlines() if line.startswith("description:"))
    assert len(description) - len("description: ") <= 1024
    assert len(text.splitlines()) < 500
    for link in ("references/workflows.md", "references/safety.md", "references/errors.md"):
        assert (src / link).exists(), link


def test_commands_reference_covers_cli():
    md = sk.commands_reference()
    for cmd in ("bili feed inbox", "bili video watch", "bili skills install", "bili dm send"):
        assert f"## `{cmd}`" in md
    assert "`risk_control`" in md


def test_plan_only_targets_detected_agents(home):
    (home / ".claude").mkdir()
    plan = by_agent(sk.plan(sk.TARGETS, None))
    assert plan["agents"]["action"] == "install"  # the shared folder is always used
    assert plan["claude-code"]["action"] == "install"
    assert plan["kiro"]["action"] == "skip: agent not installed"
    assert not (home / ".agents").exists()  # planning writes nothing


def test_install_status_uninstall_roundtrip(home):
    (home / ".claude").mkdir()
    results = by_agent(sk.install(sk.TARGETS, None, force=False))
    assert results["agents"]["done"] and results["claude-code"]["done"]
    for root in (home / ".agents", home / ".claude"):
        d = root / "skills" / sk.SKILL_NAME
        assert (d / "SKILL.md").exists() and (d / "references" / "commands.md").exists()
        assert json.loads((d / sk.MARKER).read_text())["version"]
    st = by_agent(sk.status(sk.TARGETS)["targets"])
    assert st["claude-code"]["installed"] and st["claude-code"]["up_to_date"]
    removed = sk.uninstall(sk.TARGETS, None)
    assert {r["agent"] for r in removed} == {"agents", "claude-code"}
    assert not (home / ".claude" / "skills" / sk.SKILL_NAME).exists()


def test_never_overwrites_or_removes_a_foreign_skill(home):
    foreign = home / ".claude" / "skills" / sk.SKILL_NAME
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("user's own", encoding="utf-8")
    results = by_agent(sk.install(sk.TARGETS, None, force=False))
    assert results["claude-code"]["action"].startswith("skip: a different skill")
    assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "user's own"
    sk.uninstall(sk.TARGETS, None)
    assert (foreign / "SKILL.md").exists()
    # --force replaces it, after which it is ours
    sk.install(sk.TARGETS, ["claude-code"], force=True)
    assert sk.read_marker(foreign) is not None


def test_stale_install_detected(home):
    sk.install(sk.TARGETS, ["agents"], force=False)
    marker = home / ".agents" / "skills" / sk.SKILL_NAME / sk.MARKER
    data = json.loads(marker.read_text())
    data["hash"] = "old"
    marker.write_text(json.dumps(data))
    assert by_agent(sk.status(sk.TARGETS)["targets"])["agents"]["up_to_date"] is False


def test_claude_config_dir_env_is_respected(home, monkeypatch, tmp_path):
    custom = tmp_path / "custom-claude"
    custom.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
    plan = by_agent(sk.plan(sk.TARGETS, ["claude-code"]))
    assert plan["claude-code"]["path"] == str(custom / "skills" / sk.SKILL_NAME)
