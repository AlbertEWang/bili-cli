# Install bili-cli (instructions for AI agents)

You are an AI agent and the user asked you to install bili-cli, a command-line tool that lets you operate their Bilibili (B站) account. Follow these steps in order and report the result of each one to the user.

## 1. Install the `bili` command

Pick the first option that works:

```bash
uv tool install git+https://github.com/kukemc/bili-cli     # preferred
pipx install git+https://github.com/kukemc/bili-cli         # if uv is missing
```

If neither `uv` nor `pipx` exists, install uv first (`curl -LsSf https://astral.sh/uv/install.sh | sh`, or on Windows `irm https://astral.sh/uv/install.ps1 | iex`), then run the first command.

Check: `bili --version` prints `{"ok": true, "data": {"version": ...}}`. If `bili` is not found, run `uv tool update-shell` and ask the user to open a new terminal.

## 2. Install the skill into the user's agents

```bash
bili skills install            # preview: shows which agents were found and where files go
bili skills install --yes      # write them
```

Tell the user which agents received the skill (`targets[].agent`). The skill teaches you (and other agents on this machine) how to use bili-cli safely.

## 3. Log in (needs the human)

```bash
bili auth login
```

Give the user the `qr_image` path (or `qr_url`) and ask them to scan it with the Bilibili app and confirm. Recommend scanning with an account they already use normally: Bilibili is strictest with freshly registered accounts, which hit risk control and captchas almost immediately. When they say done:

```bash
bili auth status --wait 120
```

## 4. Optional

- `bili owner set <UID>`: the user's own Bilibili UID, so you can `@` them in comments and send them private messages.
- `ffmpeg`: needed for HD frames, transcription and uploads without a cover. Suggest installing it if missing.
- `bili asr setup local`: speech-to-text for videos without subtitles (downloads a model: ~1 GB on CPU, ~4 GB with an NVIDIA GPU). Ask the user before running it.

## 5. Finish

Read the installed skill (`bili skills show`) and tell the user, in one short paragraph, what you can now do on Bilibili for them.
