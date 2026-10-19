# bili-cli

为 AI Agent 设计的哔哩哔哩命令行工具。把它交给一个 Agent，Agent 就能读视频、看评论、回复粉丝，最终自主运营一个 B 站账号。

> 状态：v0.3 开发中。已支持扫码登录、视频信息 / 字幕 / 弹幕 / AI 总结、评论读写、消息通知、发弹幕、动态、个人资料、视频投稿、搜索，以及写操作限流。路线图见 [docs/策划案.md](docs/策划案.md)。

## 安装

```bash
pipx install bili-cli        # 或 uv tool install bili-cli
# 从源码安装
pip install -e .
```

需要 Python 3.10+。

## 快速开始

```bash
bili auth login --wait 180            # 终端里显示二维码，用哔哩哔哩 App 扫码
bili video info BV1GJ411x7h7
bili video subtitle BV1GJ411x7h7 --text
bili comment list BV1GJ411x7h7 --sort hot
bili comment reply BV1GJ411x7h7 3760801399 "说得好" --dry-run
```

## 命令一览

| 命令 | 说明 |
| --- | --- |
| `bili auth login / status / logout` | 扫码登录、查看登录状态（自动刷新凭证）、登出 |
| `bili video info / stats` | 视频元数据与数据 |
| `bili video subtitle` | 字幕（含 AI 字幕，通常需要登录），`--text` 只返回纯文本 |
| `bili video danmaku` | 弹幕，按出现时间排序 |
| `bili video summary` | B 站官方 AI 总结（需要登录） |
| `bili video frames` | 抽取画面为图片，并拼一张带时间标注的总览图：默认用进度条缩略图（480x270，几秒完成，免 ffmpeg）；`-q hd` 用 ffmpeg 截取精确帧（≤720p）；支持 `--count` / `--every` / `--at` / `--chapters` 采样 |
| `bili comment list / replies` | 评论与楼中楼 |
| `bili comment post / reply / like / delete` | 发评论、回复、点赞、删除；`--type dynamic/draw/article` 用于动态和专栏评论区 |
| `bili danmaku send / recall` | 在指定时间点发弹幕；发送后短时间内可撤回 |
| `bili danmaku interact vote / rating / reserve / link / follow` | 互动弹幕（仅限自己的视频）：投票、评分、下期预告（稿件 / 直播预约）、关联视频卡片、关注 / 一键三连按钮 |
| `bili danmaku interact list / remove` | 列出组件（含投票票数、评分均分、预约人数）；删除组件，删除下期预告时会一并撤销账号上的预约 |
| `bili video chapters` | 读取任意视频进度条上的分段章节 |
| `bili video transcribe` | 语音转文字（给没有字幕的视频用），输出带时间轴，格式同 `subtitle`；结果自动缓存 |
| `bili asr setup local` | 一键部署本地转写：自动识别 NVIDIA 显卡，GPU 用 Qwen3-ASR（PyTorch，RTX 3060 上 31 分钟视频约 2 分钟），CPU 用 Qwen3-ASR int8（sherpa-onnx，免 PyTorch） |
| `bili asr setup cloud` | 配置云端转写：任何 OpenAI 兼容接口（OpenAI / Groq / 硅基流动…）、阿里云百炼 Qwen3-ASR-Flash、腾讯云一句话识别 |
| `bili asr status / use` | 查看引擎与依赖状态；设置默认引擎（配置了云端时默认用云端） |
| `bili upload chapters show / set / clear` | 给自己的稿件设置分段章节，如 `-c "0:00 开场" -c "1:30 正片"`，也可 `--file` 每行一个 |
| `bili feed notifications` | 各类未读消息数 |
| `bili feed replies / mentions` | 收到的回复和 @，每条附带可直接执行的 `reply_with` 命令 |
| `bili feed timeline` | 关注的人的最新动态 |
| `bili dynamic post / list / show / delete` | 发布文字 / 图文动态、列出、查看、删除 |
| `bili me show / set-sign / set-name / set-avatar` | 查看和修改个人资料；需要花硬币的改名必须加 `--allow-cost` |
| `bili upload video` | 上传视频投稿：分 P、封面（不传则用 ffmpeg 截帧）、自动预测分区、定时发布、仅自己可见；**默认勾选“含AI生成内容”声明** |
| `bili upload list / status` | 我的稿件与审核状态 |
| `bili search video / user` | 搜索视频和 UP 主 |
| `bili feed inbox` | 一次看完所有新消息：未读数 + 新回复、@、赞、系统通知、未读私信（读取后 B 站会标为已读） |
| `bili feed replies / mentions / likes / system` | 分别查看收到的回复、@、赞（同一内容的赞会合并）、系统通知 |
| `bili feed recommend` | 首页个性化推荐（去掉广告和直播），`--page` 换一批 |
| `bili hot search / popular / weekly / precious / rank` | 热搜榜、综合热门、每周必看、入站必刷、分区排行榜；都支持 `--unseen` 过滤已看过的视频 |
| `bili video watch` | “看”一个视频：一次返回信息、标签、AI 总结、全文（字幕，没有则自动转写）、章节、热评、画面总览图，并记入已看列表；`--record` 写入 B 站历史记录 |
| `bili owner set / show / clear` | 设置“主人”（Agent 为谁服务），之后可 `--at owner`、`dm send owner` |
| `bili comment post / reply --at <UID\|owner>` | 真正的 @（带 `at_name_to_mid`，对方会收到提醒），返回是否被 B 站识别 |
| `bili comment check` | 检查自己的评论是否正常显示（未被折叠 / 隐藏） |
| `bili dm list / read / send` | 私信：会话列表、读消息、发送 / 回复。默认只能发给主人、给你发过私信的人或互关好友；陌生人需 `--allow-new` |
| `bili schema` | 全部命令、参数和错误码的机器可读描述 |

视频 ID 支持 BV 号、av 号和视频链接。

## 执行护栏

所有写操作都会经过本地限流，超限时返回 `rate_limited` 和 `retry_after`（秒），不会偷偷等待或重试：

| 操作 | 最小间隔 | 每小时上限 |
| --- | --- | --- |
| 评论 / 回复 | 10 秒 | 30 |
| 弹幕 | 10 秒 | 30 |
| 点赞 | 3 秒 | 120 |
| 删除 | 3 秒 | 60 |
| 动态 | 60 秒 | 10 |
| 个人资料 | 30 秒 | 10 |
| 投稿 | 5 分钟 | 5 |
| 互动弹幕组件 | 30 秒 | 20 |
| 私信 | 10 秒 | 20 |

每次成功的写操作都会追加到配置目录下的 `audit.log`（JSON Lines），方便复盘 Agent 做了什么。调试时可以设置 `BILI_CLI_NO_RATE_LIMIT=1` 关闭限流。

## 给 Agent 的约定

**输出**：stdout 永远只有一个 JSON。

```json
{"ok": true, "data": {...}}
{"ok": false, "error": {"code": "not_logged_in", "message": "尚未登录。", "hint": "运行 `bili auth login` ..."}}
```

`hint` 会告诉 Agent 下一步该做什么。二维码字符画等给人看的内容只写到 stderr。

**全局参数**（可以写在命令的任意位置）：

- `--dry-run`：写操作只返回将要发出的请求，不真正执行
- `--raw`：返回 B 站接口原始数据
- `--pretty` / `--compact`：JSON 是否缩进（默认在终端缩进、在管道紧凑）

**错误码**：

| code | 退出码 | 含义 |
| --- | --- | --- |
| `invalid_argument` | 2 | 参数错误 |
| `not_logged_in` / `auth_expired` | 3 | 未登录 / 凭证失效 |
| `not_found` | 4 | 视频、评论或字幕不存在 |
| `risk_control` | 5 | 被 B 站风控拦截，降低频率 |
| `captcha_required` | 6 | 需要人工完成验证码 |
| `rate_limited` | 7 | 操作过于频繁 |
| `network_error` | 8 | 网络错误 |
| `login_pending` | 9 | 二维码还没被扫描 / 确认 |
| `login_expired` | 10 | 二维码已过期 |
| `api_error` / `internal_error` | 1 | 其他 B 站错误 / bili-cli 自身错误 |

**登录流程**：Agent 扫不了码，所以登录分两步。

1. `bili auth login` 立即返回二维码链接 `qr_url` 和图片路径 `qr_image`，Agent 把它交给人类。
2. 人类扫码后，Agent 运行 `bili auth status --wait 120` 等待结果。

**长文本**：评论正文可以用 `--file msg.txt` 或 `--file -`（stdin）传入，避免 shell 转义问题。

## 配置与凭证

凭证保存在 `%APPDATA%\bili-cli\`（Windows）或 `~/.config/bili-cli/`（Linux / macOS），可以用环境变量 `BILI_CLI_HOME` 指定其他目录，比如为不同账号准备不同的目录。

凭证文件等同于账号密码，不要提交到仓库或发给别人。

## 风险声明

本项目通过非官方接口访问哔哩哔哩，自动化操作可能触发风控，甚至导致账号被限制，风险由使用者自行承担。请遵守 B 站社区规范和相关法律法规；AI 生成的内容应按《人工智能生成合成内容标识办法》进行标识。本项目不提供、也不接受刷量、批量注册、批量控号等功能。

## 开发

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Linux / macOS: .venv/bin/pip
pytest
```

协议层基于 [bilibili-api](https://github.com/Nemo2011/bilibili-api)。

## License

MIT
