# bili-cli one-line installer (Windows PowerShell):
#   irm https://raw.githubusercontent.com/kukemc/bili-cli/main/scripts/install.ps1 | iex
# Installs the `bili` command with uv (or pipx), then installs the Agent Skill
# into the AI agents found on this machine. Set $env:BILI_NO_SKILLS = "1" to skip that step.
$ErrorActionPreference = "Stop"

$Source = if ($env:BILI_CLI_SOURCE) { $env:BILI_CLI_SOURCE } else { "git+https://github.com/kukemc/bili-cli" }

function Say($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Say "Installing bili-cli with uv"
    uv tool install --force $Source
} elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
    Say "Installing bili-cli with pipx"
    pipx install --force $Source
} else {
    Say "uv not found, installing uv first (https://docs.astral.sh/uv/)"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    uv tool install --force $Source
}

$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
if (-not (Get-Command bili -ErrorAction SilentlyContinue)) {
    Write-Warning "bili was installed but is not on PATH. Run: uv tool update-shell  (then open a new terminal)"
    exit 1
}

if ($env:BILI_NO_SKILLS -ne "1") {
    Say "Installing the bili-cli skill into your AI agents"
    bili skills install --yes --pretty
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg is not installed. It is only needed for HD frames, uploads without --cover and transcription (winget install ffmpeg)."
}

Say "Done. Next: run 'bili auth login' and scan the QR code with the Bilibili app."
