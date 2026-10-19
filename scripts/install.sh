#!/usr/bin/env sh
# bili-cli one-line installer (macOS / Linux):
#   curl -fsSL https://raw.githubusercontent.com/kukemc/bili-cli/main/scripts/install.sh | sh
# Installs the `bili` command with uv (or pipx), then installs the Agent Skill
# into the AI agents found on this machine. Set BILI_NO_SKILLS=1 to skip that step.
set -eu

SOURCE="${BILI_CLI_SOURCE:-git+https://github.com/kukemc/bili-cli}"

say() { printf '\033[1;36m==>\033[0m %s\n' "$1"; }

if command -v uv >/dev/null 2>&1; then
  say "Installing bili-cli with uv"
  uv tool install --force "$SOURCE"
elif command -v pipx >/dev/null 2>&1; then
  say "Installing bili-cli with pipx"
  pipx install --force "$SOURCE"
else
  say "uv not found, installing uv first (https://docs.astral.sh/uv/)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv installs into ~/.local/bin; make it usable in this shell
  PATH="$HOME/.local/bin:$PATH"
  uv tool install --force "$SOURCE"
fi

PATH="$HOME/.local/bin:$PATH"
if ! command -v bili >/dev/null 2>&1; then
  echo "bili was installed but is not on PATH. Run: uv tool update-shell  (then open a new terminal)" >&2
  exit 1
fi

if [ "${BILI_NO_SKILLS:-0}" != "1" ]; then
  say "Installing the bili-cli skill into your AI agents"
  bili skills install --yes --pretty
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Note: ffmpeg is not installed. It is only needed for HD frames, uploads without --cover and transcription." >&2
fi

say "Done. Next: run 'bili auth login' and scan the QR code with the Bilibili app."
