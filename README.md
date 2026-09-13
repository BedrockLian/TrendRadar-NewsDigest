# Trendradar 新闻工作台

个人私有新闻工作台：RSS采集、去重归档、固定版本简报、重大事件时间线、带引用的中文AI问答及采集/容量仪表盘。

## 运行

需要 Python 3.14、PostgreSQL 18。依赖由 `uv.lock` 锁定。

```powershell
uv sync --frozen
# 将 deploy/app.env.example 复制到 .local/dev.env，并设置数据库、独立密钥。
# 本地 HTTP 开发还需 RADAR_DEBUG=1。
uv run --env-file .local/dev.env radar migrate
uv run --env-file .local/dev.env radar admin --password-file .local/admin-password
uv run --env-file .local/dev.env python -m django collectstatic --noinput
uv run --env-file .local/dev.env radar serve
```

另开终端分别执行 `radar scheduler`、`radar worker collect`、`radar worker maintenance`、`radar worker ai`（同样传入 env 文件）。默认仅监听本机 18081 端口。

## 常用操作

```text
radar collect [--feed ID]                 创建抓取任务
radar brief [--end ISO时间]               生成简报
radar import-legacy PATH --dry-run        检查旧数据
radar import-legacy PATH                  幂等增量导入
radar maintain                           检查容量与清理
radar status                             查看容量和任务
radar verify [--ai]                       页面与真实AI连通检查
```

运行测试：`uv run --env-file .local/dev.env pytest -q`。浏览器验收脚本需要已运行的本地网页服务及 `.local/admin-password`。

线上检查：`uv run python deploy\verify_public.py --password-file .local\prod-admin-password` 会以真实登录会话核对公网边界（匿名跳转、`/api/` 返回 401、私有路径 404、静态资源、六个页面、检索与简报）。当前生产环境为 `https://news.blian117.dpdns.org`。

生产安装、备份和本次上线结果见 [运维说明](docs/operations.md)，数据与任务设计见 [架构说明](docs/architecture.md)。运行数据、凭据、截图和临时脚本统一在被忽略的 `.local/`；不要将它加入版本库。
