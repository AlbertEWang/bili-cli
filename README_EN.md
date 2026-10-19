<div align="center">

# bili-cli

**Let your AI agent run your Bilibili account — safely**

Watch · reply · DM · post · upload — one command, one JSON

[![CI](https://github.com/kukemc/bili-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/kukemc/bili-cli/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Agent Skills](https://img.shields.io/badge/Agent%20Skills-ready-8A2BE2)

[简体中文](README.md) | English

</div>

---

bili-cli is a Bilibili (B站) command-line tool **built for AI agents**. Give it to Claude Code, Codex, Cursor, Gemini CLI, OpenClaw or any agent that can run shell commands, and it can browse and understand videos, answer comments, message you, post updates and upload videos — with guardrails on by default: rate limits, an audit log, a DM allowlist and AI-content labelling.

## Install

**Tell your agent** (recommended):

```text
Install bili-cli for me by following https://raw.githubusercontent.com/kukemc/bili-cli/main/docs/install.md
```

**One line:**

```bash
curl -fsSL https://raw.githubusercontent.com/kukemc/bili-cli/main/scripts/install.sh | sh      # macOS / Linux
```

```powershell
irm https://raw.githubusercontent.com/kukemc/bili-cli/main/scripts/install.ps1 | iex           # Windows
```

**Manual:**

```bash
uv tool install git+https://github.com/kukemc/bili-cli
bili skills install --yes      # install the Agent Skill into every agent found on this machine
```

Requires Python 3.10+. ffmpeg is optional (HD frames, transcription, uploads without a cover).

## What it can do

| Capability | Example |
|---|---|
| **Understand a video** in one call: metadata, AI summary, full transcript, top comments, a contact sheet of frames; local speech-to-text when there are no subtitles | `bili video watch <BV>` |
| **Browse**: personalised recommendations, hot search, popular, weekly picks, rankings — skipping what was already watched | `bili feed recommend --unseen` |
| **Engage**: one inbox for replies / mentions / likes / DMs, each reply with a ready-to-run `reply_with` command; real @mentions | `bili feed inbox`, `bili comment post <BV> "…" --at owner` |
| **Private messages** with an anti-harassment allowlist | `bili dm send owner "…"` |
| **Create**: dynamics, uploads (AI-content declaration on by default), scheduling, review status | `bili upload video a.mp4 --title …` |
| **Creator tools**: progress-bar chapters, interactive votes / ratings / follow buttons | `bili upload chapters set` |
| **Speech-to-text**: one-command local Qwen3-ASR (GPU auto-detected; a 31-min video in ~2 min on an RTX 3060) or cloud engines | `bili asr setup local` |
| **Agent integration**: install the skill into all local agents | `bili skills install --yes` |

## Built for agents

- **One command, one JSON.** `{"ok": true, "data": …}` or `{"ok": false, "error": {"code", "message", "hint"}}` with a non-zero exit code; `hint` says what to do next.
- **Zero interaction.** QR login is split into "get the code" and "wait for the scan", so the agent just hands the QR image to a human.
- **Actionable output.** Replies come with `reply_with`, dynamics with `list_with`.
- **Context-frugal.** Compact cards, `--max-chars`, `--text`, one contact-sheet image instead of many frames.
- **Self-describing.** `bili schema` prints every command, option and error code; the skill's command reference is generated from the code at install time.
- **Prompt-injection aware.** Video, comment and DM content is marked as material, not instructions.

## Guardrails (on by default)

Per-action rate limits, an audit log of every write, `--dry-run` everywhere, a DM allowlist (owner, people who messaged you, mutual follows), the AI-content declaration on uploads, and dedicated error codes for risk control and captchas that tell the agent to stop.

## Disclaimer

bili-cli is an independent, unofficial project, not affiliated with Bilibili. It is meant for letting an AI assistant manage **your own** account. It does not provide downloading, paid content, risk-control circumvention, multi-account automation, engagement manipulation or mass messaging. See [DISCLAIMER.md](DISCLAIMER.md).

## License

[MIT](LICENSE)
