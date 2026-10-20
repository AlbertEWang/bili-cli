# 参与贡献 / Contributing

谢谢你愿意改进 bili-cli！

## 开发环境

```bash
git clone https://github.com/kukemc/bili-cli && cd bili-cli
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip
.venv/bin/pytest -q
```

测试全部离线运行，不需要 B 站账号。需要真实账号验证的改动，请用**自己已经正常使用过一段时间的账号**测试（刚注册的新号风控最严，很容易一上来就触发验证码），只在自己的内容上做写操作，测完清理掉，并在 PR 里说明测过哪些命令。

## 约定

- **输出契约。** 每条命令在 stdout 只输出一个 JSON：成功 `{"ok": true, "data": ...}`，失败通过抛 `BiliError(code, message, hint)`。给人看的进度写 stderr。不要改已有字段的含义；新增字段可以。
- **错误码。** 新的失败场景优先映射到已有错误码（`errors.py` 的 `ERROR_TABLE`），把 B 站原始码放进 `detail.bili_code`。
- **写操作。** 必须支持 `--dry-run`，经过 `guard.check()` / `guard.record()`（限流和审计日志）。
- **Agent 友好。** 输出尽量精简（Agent 的上下文很贵）；需要下一步时给出可直接执行的命令（参考 `reply_with`）。
- **技能文件。** 改了命令行为，记得同步 `skills/bili-cli/` 里的说明。`references/commands.md` 会在安装时自动生成，不用手改。
- **测试。** 新功能附带离线测试（用 `httpx.MockTransport` 或替换函数，参考 `tests/test_asr.py`）。

## 不接受的贡献

为了让项目长期、合规地存在下去，以下内容的 PR 会被直接关闭（详见 [DISCLAIMER.md](DISCLAIMER.md)）：

- 视频 / 音频下载，付费或会员内容
- 绕过验证码、风控、签名校验或访问限制
- 多账号批量操作、刷量（播放 / 点赞 / 投币 / 关注）、批量私信
- 获取他人隐私或身份信息、大规模数据采集

## 提交

- 一个 PR 做一件事；提交信息说清楚“为什么”。
- 运行 `pytest -q` 全部通过后再提交。
