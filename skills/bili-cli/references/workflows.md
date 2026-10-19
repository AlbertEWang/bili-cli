# 常用工作流

所有示例里的 `<BV>` 都可以换成 av 号或视频链接。

## 1. 处理新消息（自主运营的每一轮从这里开始）

```bash
bili feed inbox --limit 5
```

返回 `unread`（各类未读数）以及新的 `replies`、`mentions`、`likes`、`system`、`private_messages`。读取后 B 站会把它们标为已读，所以**一轮只调用一次**，并把结果记在你自己的上下文里。

- 回复评论：每条 `replies` / `mentions` 都带 `reply_with`，例如
  `bili comment reply BV1xx411c7mD 3176… --root 3147… "<回复内容>"`。只替换 `<回复内容>`，不要改 ID。
- 回复私信：`bili dm read <uid>` 看上下文，再 `bili dm send <uid> "内容"`。
- 赞和系统通知一般只需要了解，不需要回应；系统通知里出现“违规”“审核”时告诉用户。

## 2. 刷视频、挑感兴趣的看

```bash
bili feed recommend --unseen -n 12      # 个性化推荐，--page 2 换一批
bili hot popular --unseen               # 全站热门
bili hot search                         # 热搜词 → bili search video "<关键词>"
bili hot rank --zone tech --unseen      # 分区排行：all/tech/knowledge/game/…
bili hot weekly                         # 每周必看
```

先根据 `title`、`desc`、`reason`、`stat` 粗筛，只对值得的视频调用 `video watch`（它比列表命令贵得多）。`--unseen` 会跳过 `video watch` 看过的视频。

## 3. 看懂一个视频

```bash
bili video watch <BV>
```

一次返回：`title`、`desc`、`tags`、`ai_summary`（B 站官方总结，可能为空）、`transcript.text`（字幕或语音转写）、`chapters`、`hot_comments`、`frames_sheet`（9 帧画面拼成的总览图路径，能看图就打开它）。

- 只要文字：`bili video subtitle <BV> --text`
- 没字幕：`bili video transcribe <BV> --text`（需先 `bili asr setup local` 或 `asr setup cloud`）
- 看更多画面：`bili video frames <BV> --every 30`、`--chapters`、`-q hd`（精确帧，需 ffmpeg）
- 想让推荐越来越懂这个账号：`bili video watch <BV> --record`（写一次历史记录，不刷播放量）

## 4. 发表看法、@ 主人

```bash
bili owner set <主人UID>                         # 一次性设置
bili comment post <BV> "看完的感想" --at owner    # 真正的 @，主人会收到提醒
bili comment check <BV> <rpid>                   # 新号/敏感内容可能被折叠，确认一下
```

返回里的 `mentions[].resolved` 为 `true` 表示 B 站识别了这个 @。一条评论最多 @ 3 人。

## 5. 私信

```bash
bili dm list --unread
bili dm read <uid> --limit 20
bili dm send owner "今天看到一个你可能喜欢的视频：BV…"
```

默认只能发给：主人、给你发过私信的人、互关好友。给陌生人发第一条私信需要 `--allow-new`，除非用户明确要求，不要用。最长 500 字，被拒绝不要重发。

## 6. 发动态、投稿

```bash
bili dynamic post "文字内容" --image cover.png
bili upload video demo.mp4 --title "标题" --tag AI --tag 教程 --desc-file desc.txt --private
bili upload status <BV>        # 审核进度，以及 B 站实际记录的标签/分区/声明
```

投稿默认带“含AI生成内容”声明；`--private` 仅自己可见，适合先试；`--schedule 2026-10-25T20:00` 定时发布（需 2 小时到 15 天后）。分区由标题自动预测，预测不准时用 `bili upload zones` 查好再 `--zone`。

## 7. UP 主运营工具

```bash
bili upload chapters set <BV> -c "0:00 开场" -c "1:30 正片"     # 进度条分段章节
bili danmaku interact vote <BV> --question "选哪个？" --option A --option B --time 30
bili danmaku interact follow <BV> --time 60 --style triple       # 一键三连按钮
bili danmaku interact list <BV>                                  # 含投票结果、评分
```
