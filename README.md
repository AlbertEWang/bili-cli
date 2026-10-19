<div align="center">

# bili-cli

**让 AI Agent 安全地运营你的 B 站账号**

看视频 · 回评论 · 发私信 · 发动态 · 投稿，全部一条命令、一个 JSON

[![CI](https://github.com/kukemc/bili-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/kukemc/bili-cli/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Agent Skills](https://img.shields.io/badge/Agent%20Skills-ready-8A2BE2)

简体中文 | [English](README_EN.md)

</div>

---

bili-cli 是一个**为 AI Agent 设计**的哔哩哔哩命令行工具。把它交给 Claude Code、Codex、Cursor、Gemini CLI、OpenClaw 等任何能执行命令的 Agent，它就能替你刷视频、看懂视频、回复粉丝、私信主人、发动态、投稿——并且**默认带着护栏**：限流、审计日志、私信白名单、AI 内容声明。

```text
你：帮我看看 B 站有什么新消息，回复一下粉丝，再找个今天热门的科技视频看看，有意思就私信告诉我。

Agent：
$ bili feed inbox                       → 3 条新回复、1 条 @、12 个赞
$ bili comment reply BV1… 3175… "谢谢支持！下期会讲……"
$ bili hot rank --zone tech --unseen    → 挑中「我造了一块会飞的滑板…」
$ bili video watch BV1KiJk67EQ9         → AI 总结 + 字幕全文 + 热评 + 9 帧画面
$ bili dm send owner "今天科技区第二名很有意思：……"
```

## 🚀 安装

### 方式一：复制这句话发给你的 Agent（推荐）

```text
帮我安装 bili-cli，按这个说明操作：https://raw.githubusercontent.com/kukemc/bili-cli/main/docs/install.md
```

Agent 会自己装好命令、把使用技能装进你电脑上的各个 Agent，再引导你扫码登录。

### 方式二：一行命令

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/kukemc/bili-cli/main/scripts/install.sh | sh
```

```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/kukemc/bili-cli/main/scripts/install.ps1 | iex
```

安装脚本会：用 [uv](https://docs.astral.sh/uv/)（没有就先装 uv）安装 `bili` 命令 → 运行 `bili skills install --yes`，把技能装进检测到的 Agent。

### 方式三：手动

```bash
uv tool install git+https://github.com/kukemc/bili-cli    # 或 pipx install git+https://…
bili skills install          # 预览会装到哪些 Agent
bili skills install --yes    # 确认安装
```

需要 Python 3.10+。[ffmpeg](https://ffmpeg.org/) 可选（高清抽帧、语音转写、不传封面投稿时需要）。

## ✨ 能做什么

| | 能力 | 代表命令 |
|---|---|---|
| 👀 | **看懂视频**：信息、AI 总结、字幕全文、热评、画面总览图一次拿全；没字幕就本地语音转写 | `bili video watch <BV>` |
| 🔥 | **刷 B 站**：个性化推荐、热搜、综合热门、每周必看、排行榜，自动跳过看过的 | `bili feed recommend --unseen` |
| 💬 | **互动**：收件箱一次看完回复 / @ / 赞 / 私信，每条回复附带可直接执行的回复命令；真正的 @（对方会收到提醒） | `bili feed inbox`、`bili comment post <BV> "…" --at owner` |
| ✉️ | **私信**：读会话、回复；默认只能发给主人、联系过你的人或互关好友 | `bili dm send owner "…"` |
| 📝 | **创作**：图文动态、视频投稿（默认勾选“含AI生成内容”）、定时发布、稿件审核状态 | `bili upload video a.mp4 --title …` |
| 🎛️ | **UP 主工具**：进度条分段章节、投票 / 评分 / 一键三连 / 下期预告等互动弹幕 | `bili upload chapters set`、`bili danmaku interact vote` |
| 🎙️ | **语音转写**：一键部署本地 Qwen3-ASR（有 NVIDIA 显卡自动用 GPU，31 分钟视频约 2 分钟），或接云端服务 | `bili asr setup local` |
| 🧩 | **装进 Agent**：一条命令给本机所有 Agent 装上使用技能 | `bili skills install --yes` |

## ⚡ 30 秒上手

```bash
bili auth login               # 返回二维码图片路径，用 B 站 App 扫码
bili auth status --wait 120   # 等扫码完成
bili feed inbox               # 看新消息
bili video watch BV1GJ411x7h7 # 看一个视频
bili owner set <你的UID>       # 告诉 Agent 谁是主人，之后可以 @ 你、私信你
```

## 🤖 为 Agent 而生

- **一条命令，一个 JSON。** 成功 `{"ok": true, "data": …}`，失败 `{"ok": false, "error": {"code", "message", "hint"}}`，退出码非 0。`hint` 直接告诉 Agent 下一步该做什么。
- **零交互。** 不弹确认、不读键盘；扫码登录拆成“生成二维码”和“等待结果”两步，Agent 把二维码交给人类即可。
- **下一步可执行。** 收到的回复带 `reply_with`，动态带 `list_with`，Agent 不用自己拼 ID。
- **省上下文。** 列表精简成卡片，长文本有 `--max-chars` / `--text`，画面拼成一张总览图。
- **自描述。** `bili schema` 输出全部命令、参数、错误码；技能里的命令手册在安装时根据代码自动生成，永远不会过期。
- **防提示注入。** 视频、评论、私信内容都标注为“素材而非指令”，技能里也写明了这条规则。

<details>
<summary><b>错误码</b></summary>

| code | 退出码 | 含义 |
| --- | --- | --- |
| `invalid_argument` | 2 | 参数错误 |
| `not_logged_in` / `auth_expired` | 3 | 未登录 / 凭证失效 |
| `not_found` | 4 | 资源不存在 |
| `risk_control` | 5 | 被 B 站风控拦截，应停止写操作 |
| `captcha_required` | 6 | 需要人工完成验证码 |
| `rate_limited` | 7 | 操作过于频繁，按 `retry_after` 等待 |
| `network_error` | 8 | 网络错误 |
| `login_pending` / `login_expired` | 9 / 10 | 二维码未扫 / 已过期 |
| `api_error` / `internal_error` | 1 | 其他 B 站错误 / bili-cli 自身错误 |

</details>

## 🛡️ 安全护栏

用的是你自己的账号，所以护栏是默认开启的，而不是可选项：

| 护栏 | 说明 |
|---|---|
| 本地限流 | 评论 10 秒/次、30 次/小时；私信 10 秒/次、20 次/小时；动态 60 秒/次；投稿 5 分钟/次……超限立即返回 `rate_limited`，不偷偷重试 |
| 审计日志 | 每个写操作都记入配置目录的 `audit.log`，随时复盘 Agent 做了什么 |
| `--dry-run` | 所有写操作都能先预览 |
| 私信白名单 | 默认只能发给主人、给你发过私信的人、互关好友，陌生人需显式 `--allow-new` |
| AI 内容声明 | 投稿默认勾选“含AI生成内容”，符合《人工智能生成合成内容标识办法》 |
| 风控即停 | 遇到风控 / 验证码返回专门的错误码，技能要求 Agent 立刻停止并告诉你 |

## 🧩 支持的 Agent

`bili skills install` 会把技能写进 `~/.agents/skills/bili-cli`（[Agent Skills](https://agentskills.io) 标准位置），并给检测到的其他 Agent 各写一份：

Claude Code · OpenAI Codex · Cursor · Gemini CLI · GitHub Copilot · Windsurf · Roo Code · OpenCode · OpenClaw · Qwen Code · Kiro · Cline · Trae · CodeBuddy · 通义灵码 · Qoder · iFlow · Goose

只写入你电脑上已经存在的 Agent 目录；不会覆盖你自己的同名技能；`bili skills uninstall --yes` 干净卸载。也可以用 `npx skills add kukemc/bili-cli` 安装。

### MCP（给不能执行命令的客户端）

Claude Desktop、Cherry Studio 等只支持 MCP 的客户端，可以用 MCP 模式：

```bash
uv tool install --force "bili-cli[mcp] @ git+https://github.com/kukemc/bili-cli"
bili mcp install            # 预览：检测到哪些客户端（Claude Desktop、Claude Code、Cursor、VS Code、Codex、Gemini CLI）
bili mcp install --yes      # 写入配置（先备份为 .bak，只增改 bili-cli 自己的条目）
```

提供 17 个工具：收件箱、看视频、搜索、推荐、热门、评论、回复、私信、动态等，外加一个可以调用任意命令的 `run_bili`。写操作的工具标记为非只读，支持的客户端会先征求你的同意。手动配置时，命令是 `bili mcp serve`。

<details>
<summary><b>📖 全部命令</b></summary>

| 命令 | 说明 |
| --- | --- |
| `bili auth login / status / logout` | 扫码登录、登录状态（自动续期）、登出 |
| `bili video info / stats / subtitle / danmaku / summary / chapters` | 视频信息、数据、字幕、弹幕、AI 总结、分段章节 |
| `bili video watch` | 一次拿全：信息 + 标签 + AI 总结 + 全文 + 章节 + 热评 + 画面总览图；`--record` 写入历史记录 |
| `bili video frames` | 抽帧并拼总览图：默认用进度条缩略图（快、免 ffmpeg），`-q hd` 精确帧；`--count/--every/--at/--chapters` |
| `bili video transcribe` | 语音转文字，格式同字幕，结果缓存 |
| `bili feed inbox` | 一次看完所有新消息（读取后 B 站标为已读） |
| `bili feed replies / mentions / likes / system / notifications` | 回复、@、赞、系统通知、未读数 |
| `bili feed recommend / timeline` | 首页推荐、关注动态 |
| `bili hot search / popular / weekly / precious / rank` | 热搜、综合热门、每周必看、入站必刷、排行榜 |
| `bili search video / user` | 搜索 |
| `bili comment list / replies / post / reply / like / delete / check` | 评论读写；`--at <UID|owner>` 真正的 @；`--type dynamic/draw/article` 用于动态和专栏 |
| `bili dm list / read / send` | 私信 |
| `bili owner set / show / clear` | 设置“主人” |
| `bili dynamic post / list / show / delete` | 动态 |
| `bili danmaku send / recall` | 发 / 撤回弹幕 |
| `bili danmaku interact vote / rating / reserve / link / follow / list / remove` | 互动弹幕（仅自己的视频） |
| `bili upload video / list / status / zones` | 投稿与稿件管理 |
| `bili upload chapters show / set / clear` | 分段章节 |
| `bili me show / set-sign / set-name / set-avatar` | 个人资料 |
| `bili asr setup local / setup cloud / status / use` | 语音转写引擎 |
| `bili skills install / uninstall / status / show` | 把技能装进 Agent |
| `bili mcp serve / install / uninstall` | MCP 服务与客户端配置 |
| `bili schema` | 机器可读的完整命令描述 |

全局参数可写在任意位置：`--dry-run`、`--raw`（B 站原始数据）、`--pretty` / `--compact`。所有视频参数接受 BV 号、av 号或链接。

</details>

## ❓ 常见问题

<details>
<summary>会不会被封号？</summary>

自动化操作总有风险，尤其是新注册的账号（B 站会对新号的投稿、评论、私信做更严格的风控）。bili-cli 默认限流、遇到风控立刻停止，并且不提供任何绕过风控的手段。建议先用小号试用，正常使用节奏不要超过真人。

</details>

<details>
<summary>没有字幕的视频怎么办？</summary>

运行一次 `bili asr setup local`：有 NVIDIA 显卡（显存 ≥4GB）自动部署 GPU 版 Qwen3-ASR（RTX 3060 上 31 分钟视频约 2 分钟），否则部署 CPU 版（无需 PyTorch，约 0.45 倍实时）。也可以 `bili asr setup cloud` 接 OpenAI 兼容接口、阿里云百炼或腾讯云。之后 `video watch` 遇到无字幕视频会自动转写。

</details>

<details>
<summary>多个账号怎么办？</summary>

设置环境变量 `BILI_CLI_HOME` 指向不同目录，每个目录是一套独立的登录、限流和审计日志。本项目不提供批量控制多账号的功能。

</details>

<details>
<summary>凭证存在哪里？安全吗？</summary>

Windows 在 `%APPDATA%\bili-cli\`，其他系统在 `~/.config/bili-cli/`（权限 600）。只会发给 B 站自己的服务器。详见 [SECURITY.md](SECURITY.md)。

</details>

## 🤝 参与贡献

欢迎 Issue 和 PR，开发约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。更新记录见 [CHANGELOG.md](CHANGELOG.md)。

## ⚠️ 免责声明

bili-cli 是独立的非官方项目，与哔哩哔哩没有关联。它用于让 AI 助手**管理你自己的账号**，不提供也不接受下载、付费内容、绕过风控、多账号、刷量、批量私信等功能。使用产生的后果由使用者自行承担，请遵守法律法规、B 站用户协议与社区规则，并对 AI 生成内容进行标识。完整内容见 [DISCLAIMER.md](DISCLAIMER.md)。

## License

[MIT](LICENSE)
