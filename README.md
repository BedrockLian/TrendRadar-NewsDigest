# Trendradar

[![Quality](https://github.com/BedrockLian/TrendRadar-NewsDigest/actions/workflows/quality.yml/badge.svg)](https://github.com/BedrockLian/TrendRadar-NewsDigest/actions/workflows/quality.yml)

面向个人使用的生产级新闻情报工作站。Trendradar 持续采集 RSS，将报道去重、版本化并归档，按固定时间生成可追溯简报，再通过 DeepSeek Responses API 自动生成中文标题与简介、发现重大事件并维护带引用的事件时间线。

界面采用 Django 模板、HTMX 和原生 JavaScript，支持浅色、深色与跟随系统三种主题。系统以单管理员、私有部署为边界，不包含多租户和公开注册流程。

## 核心能力

- 普通源每 10 分钟、重点源每 2 分钟采集；支持条件请求、退避和来源健康统计。
- 通过规范化 URL、源内 GUID 与内容指纹去重，同时保留跨来源报道和内容版本。
- 在北京时间 08:00、12:30、20:00 生成固定版本简报，引用不会随原文更新而漂移。
- 自动生成中文标题和简介；AI 不可用时，采集、检索和原文简报仍可运行。
- AI 自动发现、更新并结束重大事件；正式节点始终保存固定报道版本作为证据。
- PostgreSQL 全文检索、游标分页、容量清理、小时统计和任务租约恢复。
- 首页简报优先，另有新闻归档、事件时间线、采集仪表盘和带引用的新闻库问答。

## 技术架构

```text
RSS -> PostgreSQL 持久任务 -> 采集 Worker -> 文章与内容版本
                                      |-> 固定版本简报
                                      |-> AI 中文内容
                                      |-> 重大事件与时间线

Django + HTMX -> PostgreSQL 18 <- 调度器 / 采集 Worker / AI Worker / 维护 Worker
```

| 组件 | 版本与用途 |
| --- | --- |
| Python | 3.14 |
| Django | 5.2 LTS |
| PostgreSQL | 18，业务数据、全文检索与持久任务队列 |
| AI | DeepSeek Responses API，通过 OpenAI Python SDK 调用 |
| Web | Uvicorn；生产环境由 HTTPS 反向代理接入 |
| 依赖管理 | uv 与锁定的 `uv.lock` |

详细边界见 [架构说明](docs/architecture.md)。

## 本地启动

准备 Python 3.14、PostgreSQL 18 和 [uv](https://docs.astral.sh/uv/)，然后在仓库根目录执行：

```powershell
uv sync --frozen
Copy-Item deploy/app.env.example .local/dev.env
# 编辑 .local/dev.env：配置 DATABASE_URL、RADAR_SECRET_KEY，并将 RADAR_DEBUG 设为 1。
uv run --env-file .local/dev.env radar migrate
uv run --env-file .local/dev.env radar admin --password-file .local/admin-password
uv run --env-file .local/dev.env python -m django collectstatic --noinput
uv run --env-file .local/dev.env radar serve
```

网页默认监听 `127.0.0.1:18081`。完整运行还需在独立终端启动：

```powershell
uv run --env-file .local/dev.env radar scheduler
uv run --env-file .local/dev.env radar worker collect
uv run --env-file .local/dev.env radar worker maintenance
uv run --env-file .local/dev.env radar worker ai
```

`DEEPSEEK_API_KEY` 可以留空；缺少密钥时只有 AI 功能停用。所有秘密配置都应保存在 `.local/` 或服务器私有配置中。

## 常用命令

```text
radar collect [--feed ID]                    创建采集任务
radar brief [--end ISO时间]                  生成简报
radar ai-backfill [--scope all] [--limit N]  回填缺少中文内容的新闻
radar events-auto [--batches N]              立即执行重大事件发现与复核
radar import-legacy PATH --dry-run            预检旧数据迁移
radar maintain                               执行容量检查与清理
radar status                                 查看存储和任务状态
radar verify [--ai]                          验证页面及可选的真实 AI 请求
```

## 质量检查

测试使用真实 PostgreSQL，不支持用 SQLite 替代：

```powershell
uv run ruff check app tests
uv run ruff format --check app tests
uv run --env-file .local/dev.env python -m django check
uv run --env-file .local/dev.env pytest -q
```

启动本地服务后，可运行 `uv run python tests/browser_redesign.py` 检查 1440、1024、390 和 320 像素视口、双主题、归档阅读区及移动端交互。截图和报告只写入 `.local/`。

## 生产部署

部署工具面向使用 systemd 的 Linux 服务器。安装器建立低权限账号、PostgreSQL、五个服务和私有配置，但不会替你修改现有反向代理：

```bash
RADAR_PUBLIC_HOST=news.example.com \
  bash deploy/install.sh /opt/trendradar-next/releases/20260101-01
```

切换流量、更新、备份恢复和容量处置步骤见 [运维说明](docs/operations.md)。执行迁移或切换前必须先完成离机备份与恢复验证。

## 仓库边界

仓库只保存应用代码、数据库迁移、测试、静态资源、通用部署工具和长期文档。以下内容不会发布：

- `.local/`、`.env*` 中的账号、密钥和服务器配置；
- PostgreSQL 数据、新闻归档、备份、日志、截图和浏览器测试产物；
- 服务器发布目录、虚拟环境和生成后的静态文件；
- 针对某一次迁移、域名切换或旧服务器删除的一次性脚本与发布记录。

自托管 Geist 字体位于 `app/ui/static/fonts/`，并附带原始 OFL 许可；HTMX 作为浏览器运行依赖随仓库分发。

## 使用与授权

本仓库未授予开源许可，项目代码保留所有权利。仓库中的第三方资源继续适用各自的许可声明，例如 `app/ui/static/fonts/LICENSE.txt` 中的 Geist 字体 OFL 许可。
