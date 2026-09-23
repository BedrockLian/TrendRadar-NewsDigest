# 运维说明

本文档面向单机 Linux 生产部署。示例使用 `/opt/trendradar-next`，数据库、秘密配置和发布版本相互分离。不要把真实域名、账号、密钥、备份名和单次发布记录提交到仓库。

## 目录与服务

```text
/opt/trendradar-next/
├─ bin/uv
├─ python/
├─ releases/<version>/
├─ current -> releases/<version>
└─ postgres18/              # 只有源码编译安装时存在

/etc/trendradar-next/app.env       # 0640 root:radar
/etc/trendradar-next/admin-password
/var/lib/trendradar-next/
```

systemd 单元：

- `trendradar-next-web`：Uvicorn 网页服务；
- `trendradar-next-scheduler`：创建到期任务；
- `trendradar-next-collect`：RSS 采集；
- `trendradar-next-ai`：翻译、事件和问答；
- `trendradar-next-maintenance`：简报、容量与其他维护任务。

## 首次安装

安装器支持 OpenCloudOS、Rocky/Alma/RHEL 系和 Debian/Ubuntu。它会安装 Python 3.14、PostgreSQL 18、创建 `radar` 账号和 systemd 单元，但只启动 Web 服务。

```bash
export RADAR_PUBLIC_HOST=news.example.com
export RADAR_PUBLIC_ORIGIN=https://news.example.com
bash deploy/install.sh /opt/trendradar-next/releases/20260101-01
```

安装后完成以下步骤：

1. 在 `/etc/trendradar-next/app.env` 写入 `DEEPSEEK_API_KEY`（如需 AI）。
2. 将 HTTPS 反向代理指向 `127.0.0.1:18081`，并传递 `Host`、`X-Forwarded-Proto`。
3. 在本机验证 `/health/`、登录和数据库迁移。
4. 启用调度器和 Worker：

```bash
systemctl enable --now \
  trendradar-next-scheduler \
  trendradar-next-collect \
  trendradar-next-ai \
  trendradar-next-maintenance
```

## 安全设置

- PostgreSQL 只监听 `127.0.0.1`，不开放公网端口。
- 生产环境保持 `RADAR_DEBUG=0`，并使用独立 `RADAR_SECRET_KEY`。
- 管理员口令通过文件传入，不放在 shell 参数或环境输出中。
- `/etc/trendradar-next/app.env` 仅 root 和 `radar` 组可读。
- 上游代理必须提供 HTTPS；应用依赖同源会话和 CSRF 保护。

更换管理员：

```bash
install -m 600 /dev/null /root/trendradar-admin-password
# 以安全方式写入新口令，不要在命令行中明文传入。
bash deploy/run.sh admin \
  --username NEW_ADMIN \
  --retire OLD_ADMIN \
  --password-file /root/trendradar-admin-password
rm -f /root/trendradar-admin-password
```

## 发布与回退

每次更新使用新的不可变目录，不要直接覆盖 `current`：

1. 在独立目录同步代码并执行 `uv sync --frozen --no-dev`。
2. 检查可用空间，执行离机备份并试恢复。
3. 运行 `radar migrate`和 `collectstatic --noinput`。
4. 先在本机端口验证新版本，再原子切换 `current` 符号链接。
5. 重启五个单元，检查日志和公网边界。

公网验证：

```bash
RADAR_TEST_URL=https://news.example.com \
  uv run python deploy/verify_public.py \
  --username ADMIN \
  --password-file /path/to/protected/password
```

若新版本失败，将 `current` 指回上一版，重启服务。只有在数据库迁移允许回退时才能单独回退应用；否则使用已验证的备份恢复数据库。

## 备份与恢复

服务器通过 `deploy/backup.sh` 向标准输出写入 PostgreSQL 自定义格式备份，不在服务器长期保留完整副本。Windows 工作站可使用：

```powershell
$env:RADAR_BACKUP_HOST = 'your-ssh-alias'
uv run python deploy/backup.py `
  --directory "$HOME\Documents\Trendradar-backups" `
  --pg-restore 'C:\path\to\pg_restore.exe'

powershell -File deploy/register-backup.ps1 -HostName 'your-ssh-alias'
```

保留策略为 7 份最近日备份和 4 份周备份。备份只有在 `pg_restore --list` 成功后才记为完成。定期将备份恢复到独立数据库，再核对文章、简报、事件和管理员登录。

## 日常检查

```bash
bash deploy/run.sh status
systemctl --no-pager --full status 'trendradar-next-*'
journalctl -u trendradar-next-web -u trendradar-next-ai --since today
curl --fail http://127.0.0.1:18081/health/
```

仪表盘应同时检查采集成功率、来源连续失败、任务积压、AI 用量、数据库体积、文件系统剩余空间和最近备份时间。

## 容量处置

- 数据库接近预算或磁盘剩余不足 8GB 时，维护任务分批删除最旧的非保护新闻。
- 简报、已确认事件、收藏及它们引用的内容版本不会自动删除。
- 剩余不足 6GB 时系统暂停采集、AI 和批量写入。先扩容或解除保护，不要在低空间下执行 `VACUUM FULL`。
- 普通删除释放的空间优先供 PostgreSQL 重用，不一定立即归还文件系统。

## 故障处理

- **RSS 连续失败**：检查 HTTP 状态、条件请求、超时和来源退避；`304` 应记为成功。
- **AI 无输出**：同时检查 Responses API 的 HTTP 状态、`response.incomplete`、结构化 JSON、每日额度和任务租约。
- **任务卡住**：过期租约会自动回收；确认 Worker 在运行后再人工重排。
- **翻译积压**：保留简报、突发和事件任务优先级，用 `radar ai-backfill` 分批处理历史数据。
- **额度耗尽后简报未翻译**：检查当日 `ai_usageday.used`、`lane_used` 和待执行 `enrich` 任务。常规任务按时段释放额度；事件、在线新闻和迁入的历史新闻的日上限分别为总额的 40%、40% 和 10%，简报与交互请求保留剩余 10%。提高每日上限前先核对实际用量与翻译覆盖率，设置变更不会自动清除已用 token。
- **事件过多**：新事件需要至少两个独立来源或明确突发标记；使用 `radar events-auto --audit-now` 复核自动管理事件。
