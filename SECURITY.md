# Security Policy

## Your credentials

bili-cli stores the Bilibili login cookie (`credential.json`) and transcription API keys (`asr.json`) in the local config directory:

- Windows: `%APPDATA%\bili-cli\`
- macOS / Linux: `$XDG_CONFIG_HOME/bili-cli/` (default `~/.config/bili-cli/`)

On macOS / Linux these files are written with `0600` permissions. Treat them like a password: never commit, share or paste them, and never let an agent print them. `bili auth logout` deletes the local login; to revoke the session everywhere, log out of other devices in the Bilibili app.

bili-cli never sends your credentials anywhere except Bilibili's own servers, and transcription keys only to the provider you configured.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Use GitHub's private vulnerability reporting (Security → Report a vulnerability) on this repository. We aim to respond within 7 days.

In scope: credential leaks, unsafe file permissions, command injection, an agent being able to bypass bili-cli's guardrails (rate limits, DM allowlist, AI declaration), prompt-injection paths that make bili-cli execute instructions found in video/comment/DM content.
