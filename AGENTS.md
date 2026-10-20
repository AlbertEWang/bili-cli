# AGENTS.md

Guidance for AI coding agents working **on** this repository. (To *use* bili-cli, read `skills/bili-cli/SKILL.md`.)

## Layout

- `src/bili_cli/main.py` — Typer app, global flags, `bili schema`.
- `src/bili_cli/commands/*.py` — one module per command group (`video`, `comment`, `feed`, `dm`, `upload`, …).
- `src/bili_cli/runtime.py` — `run()` wraps every command body; `web_client()` for direct HTTP calls (browser headers avoid HTTP 412).
- `src/bili_cli/errors.py` — `BiliError` and the error-code table; maps Bilibili codes to our codes.
- `src/bili_cli/guard.py` — local rate limits and the audit log for write operations.
- `src/bili_cli/asr/` — transcription (audio → VAD segments → local or cloud engine).
- `src/bili_cli/skills.py`, `commands/skills.py` — Agent Skill installer; `skills/bili-cli/` is the skill itself.
- `src/bili_cli/mcp_server.py`, `commands/mcp.py` — MCP server and client registration.

## Rules

1. **Output contract.** A command body is an `async def body()` returning a dict, run via `run(body)`; it prints `{"ok": true, "data": …}`. Fail with `raise BiliError(code, message, hint=…)`. Human-only text goes to stderr via `output.info`.
2. **Write operations** must honour `output.settings.dry_run` and call `guard.check(action)` before and `guard.record(action, params, result)` after.
3. **Keep output small**: agents pay for every token. Prefer compact cards and ready-to-run follow-up commands (see `reply_with`).
4. **Never** add downloading, paid content, captcha / risk-control / signature circumvention, multi-account automation, engagement farming or mass messaging (see DISCLAIMER.md).
5. **Tests are offline.** Mock HTTP with `httpx.MockTransport` or monkeypatch functions. Anything that touches the home directory must use a temp dir; never write to the real `~/.agents`, `~/.claude` or the user's config dir from tests.
6. When command behaviour changes, update `skills/bili-cli/` and the README; `references/commands.md` is generated at install time.

## Commands

```bash
pip install -e ".[dev]"
pytest -q
bili schema --pretty      # every command, option and error code
```
