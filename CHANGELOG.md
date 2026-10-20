# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.2.0] - 2026-10-20

### Added
- 发布到 PyPI，包名 `bili-agent`（`bili-cli` 已被占用），安装只要 `uv tool install bili-agent`；命令仍是 `bili`。打 `v*` 标签后自动发布。
- `bili skills install / uninstall / status / show`：把 Agent Skill 装进本机的 Claude Code、Codex、Cursor、Gemini CLI、Copilot、OpenClaw、Qwen Code 等 AI Agent（只写入已检测到的 Agent，不覆盖用户自己的同名技能）。
- 一行安装脚本 `scripts/install.sh`、`scripts/install.ps1`，以及给 Agent 看的安装指南 `docs/install.md`。
- MCP 模式：`bili mcp serve`（17 个工具，写操作带非只读标注，行为和护栏与命令行完全一致）；`bili mcp install / uninstall` 注册到 Claude Desktop、Claude Code、Cursor、VS Code、Codex、Gemini CLI（先备份，只改自己的条目）。安装 `bili-agent[mcp]`。
- `DISCLAIMER.md`、`SECURITY.md`、`CONTRIBUTING.md`。
- `bili video like / coin / fav / triple / relation`、`bili me favs`：点赞、投币、收藏到指定收藏夹、一键三连、查看我和视频的关系。投币必须显式指定个数，本地每 24 小时最多 5 个；对没看过的视频操作会提示。
- Logo、Banner，README 重写。

## [0.1.0] - 2026-10-20

首个版本。

- 扫码登录（两步走，适合 Agent），凭证本地保存。
- 看视频：信息、字幕、弹幕、AI 总结、分段章节、画面抽帧与总览图、语音转写（本地 Qwen3-ASR GPU/CPU，或云端 OpenAI 兼容 / 阿里云 / 腾讯云），`video watch` 一次拿全。
- 刷视频：首页推荐、热搜、综合热门、每周必看、入站必刷、排行榜，`--unseen` 跳过看过的。
- 互动：评论读写、真正的 @（`at_name_to_mid`）、评论可见性检查、消息收件箱（回复 / @ / 赞 / 系统通知 / 私信）、私信收发（带防骚扰白名单）。
- 创作：动态、投稿（默认“含AI生成内容”声明、自动预测分区、定时、仅自己可见）、稿件状态、分段章节、互动弹幕（投票、评分、下期预告、关联视频、关注 / 三连按钮）、个人资料。
- 护栏：所有写操作本地限流 + 审计日志，`--dry-run` 预览，统一 JSON 输出与错误码。
