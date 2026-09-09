# 分时新闻简报

本 fork 会每 30 分钟抓取一次全部已配置 RSS 源，并把原始数据保存到 SQLite。抓取和推送相互独立：普通新闻只会进入北京时间 08:00、12:30、20:00 的简报；命中强突发词的新闻可以在三个时段之外立即提醒。

## 简报规则

- 每期最多 20 篇，以标准化 URL、规范化标题和相似标题去重。
- 已入选的普通新闻不会在下一时段重复出现；标题、摘要或发布时间出现实质更新后，可以用“更新”标记再次入选。
- 单一来源默认最多 2 篇，内容不足时才放宽限制。
- 科技与 AI 6 篇、游戏 4 篇、社会与文化 4 篇、中国与国际关系 3 篇、全球公共事务 2 篇、日本与韩国 1 篇。某板块不足时，空缺名额按评分让给其他板块。
- 简介为单行纯文本，最长 100 字符，并附原新闻链接。没有 AI Key 时使用 RSS 自带摘要；配置 Key 后生成中文短简介。

配置集中在 `config/config.yaml` 的 `digest` 段，时间窗口位于 `config/timeline.yaml` 的 `news_digest` 预设。

## 存档和周报

简报会写入：

```text
output/briefings/YYYY-MM/YYYY-MM-DD-HHMM-时段.md
```

突发提醒写入 `output/briefings/alerts/`，每周日 20:00 的简报同时生成 `output/briefings/weekly/YYYY-Www.md`。程序只保留最近 30 天的简报和状态。GitHub Actions 会把这些 Markdown 文件及去重状态提交回 fork，Docker 部署则由持久化的 `output` 目录保存。

## 启用 AI

在 fork 的 **Settings → Secrets and variables → Actions** 中新增：

- `AI_API_KEY`：服务商密钥。
- `AI_MODEL`：可选，例如 `deepseek/deepseek-chat` 或 `openai/gpt-4o-mini`。
- `AI_API_BASE`：仅在使用兼容接口或中转服务时填写。

密钥只通过运行环境读取，不要写入仓库。没有密钥或调用失败时，简报和统计版周报仍会正常生成。

## 启用通知

在同一 Secrets 页面配置任一现有通知渠道，例如 `FEISHU_WEBHOOK_URL`、`TELEGRAM_BOT_TOKEN` 与 `TELEGRAM_CHAT_ID`、`DINGTALK_WEBHOOK_URL` 或邮件相关 Secret。未配置渠道时，程序只采集并生成 Markdown 存档。

GitHub 的定时任务可能存在几分钟延迟，因此每个简报窗口保留一小时，并用状态记录保证窗口内只成功推送一次。也可以从 Actions 页面手动运行工作流。
