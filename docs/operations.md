# 安装、迁移、备份与恢复

## 当前部署布局

- `/opt/trendradar-next/releases/版本`：不可变发布版本及该版本虚拟环境。
- `/opt/trendradar-next/current`：当前发布链接。
- `/opt/trendradar-next/python`、`bin/uv`：独立Python运行时与uv。
- `/opt/trendradar-next/postgres18`、`/var/lib/trendradar-postgres`：OpenCloudOS独立PostgreSQL程序与数据。
- `/etc/trendradar-next/app.env`：私有环境配置，root:radar 0640。
- `/var/lib/trendradar-next`：应用可写状态目录，与数据库共享磁盘。

OpenCloudOS 9的库版本与PGDG RPM不匹配，因此安装器下载、校验并编译官方PostgreSQL 18.6源码，不替换系统库。Debian/Ubuntu走PGDG，RHEL兼容系统走官方RPM。实例只绑定127.0.0.1；2GB服务器使用128MB shared_buffers、2MB work_mem、30连接上限，每应用进程连接池最大3。

## 初次安装

上传整个受版本控制的源码至新的release目录，执行：

```sh
bash deploy/install.sh /opt/trendradar-next/releases/VERSION
```

安装器启动18081隔离网页服务，暂不启用后台。通过`deploy/run.sh`自动加载私有环境：

```sh
bash /opt/trendradar-next/current/deploy/run.sh import-legacy /opt/trendradar --dry-run
bash /opt/trendradar-next/current/deploy/run.sh import-legacy /opt/trendradar
bash /opt/trendradar-next/current/deploy/run.sh verify --ai
```

`--ai`会产生一次真实模型请求。初始化密钥如存在则从旧环境迁移，模型按新系统设置使用Responses。管理员密码写入`/etc/trendradar-next/admin-password`，不打印；请通过SSH传到自己的受保护本地位置。

## 域名切换

当前安装适配宝塔Nginx新闻站。`deploy/switch.sh`等待旧采集结束、执行最后增量导入、备份该站代理规则，只将18080改为18081并补充HTTPS转发和SSE配置。Nginx检查失败则恢复代理和旧定时器。切换后验证公网登录、私有路由、页面与真实抓取，再删除旧仓库。

旧仓库清理必须先有离机备份。`deploy/remove-legacy.sh --verified-backup-and-cutover`要求备份标记和新域名健康检查通过，验证目标精确为`/opt/trendradar`后删除，仅清理旧服务定义。

## 日常检查

```sh
bash /opt/trendradar-next/current/deploy/run.sh status
systemctl status trendradar-next-web trendradar-next-scheduler trendradar-next-collect trendradar-next-ai trendradar-next-maintenance
journalctl -u trendradar-next-collect --since '1 hour ago'
```

采集单源429是来源限流，不等于部署失败。任务失败可通过原始页面操作重新提交，生成缓存防止重复处理相同AI输入。容量任务每小时执行；低空间暂停时应先检查数据库膨胀、其他服务占用及保护内容规模，避免贸然重建索引占满磁盘。

## Windows离机备份

```powershell
.venv\Scripts\python.exe deploy\backup.py
.venv\Scripts\python.exe deploy\backup.py --mark-legacy-backed-up   # 归档已验证时可解锁旧仓库清理
powershell -File deploy\register-backup.ps1
```

每日03:30通过SSH流式生成压缩自定义格式备份到`Documents\Trendradar-backups`，本机pg_restore能读取后才写成功标记并通知服务器。保留最近7份及4个自然周代表备份。任务在当前用户登录期间执行，电脑离线或退出登录会延后；超过48小时无成功备份时仪表盘告警。SSH密钥需当前用户可用。

`--mark-legacy-backed-up`只在备份文件已通过本地校验后写入`/etc/trendradar-next/legacy-backed-up`；`remove-legacy.sh`缺少该标记就拒绝删除旧仓库。删除是不可逆操作，只能在确认域名已切换且验证通过后使用。

备份文件含私人新闻、问答和密码哈希，目录应只允许当前用户访问。服务器配置秘密另保存在本地受保护备份中，不进入源码仓库。

## 恢复与版本更新

先使用**新建的隔离数据库**验证备份，不直接覆盖在线库：使用`pg_restore --no-owner --no-acl --dbname=隔离数据库 BACKUP.dump`，比较文章、版本、简报和引用数，并运行`radar verify`。数据库连接密码通过环境变量提供，不写命令行。

正式恢复：暂停所有新系统Worker和网页，创建替代数据库、恢复已验证备份，更改私有环境中的数据库地址，执行对应版本的迁移和验证后重启。保留故障库直至确认恢复；同机空间不够时先在外部主机完成恢复验证。

后续更新先执行离机备份，上传新的release，停止旧Worker，安装锁定依赖、执行迁移、收集静态文件、切换current链接、重启服务并验证。数据库不兼容迁移的回退必须配套备份，不能仅切回旧代码。不要把现场秘密配置复制进release。

## 验证入口

- `pytest -q`：真实PostgreSQL集成测试。
- `tests/browser_smoke.py`：本地桌面/手机交互与截图。
- `deploy/verify_public.py --password-file <本地密码文件>`：对已上线域名做公网边界验证（匿名页面跳转、`/api/` 返回401 JSON、私有路径404、静态资源、登录后的六个页面、搜索与简报列表）。
- `radar benchmark --count 1000000 --confirm-test-database`：只允许名称以`_benchmark`结尾的隔离数据库；耗时写入仅在该会话关闭语句超时，查询仍为30秒。
- `.local/qa`、`.local/benchmark-result.json`：本次验证产物，不提交。

单机部署具备崩溃恢复与离机备份，不等同于多机高可用。磁盘约30GB限制的是保留规模；需要更长历史时可以独立扩容数据库，无需更换业务架构。

## 本次上线记录（2026-09-13）

从旧工作台迁移到本仓库的在服务器上的实际结果，供后续核对：

| 项目 | 结果 |
|---|---|
| 历史导入 | 3607篇文章、5748个版本、25份简报、240条简报引用、58个订阅源 |
| 迁移的中文内容 | 2965个版本带中文标题/简介 |
| 切换后实时采集 | 52次请求，成功51、失败1（Washington Post World 返回503，属来源侧）；新增1198、更新571、重复878 |
| 单源抓取耗时 | p50 486ms、p95 1588ms；最慢 OpenAI News 11.9s（上限20s） |
| 百万篇合成压测 | 1,000,000篇、库4.11GB、导入220s；首页/深游标/全文检索P95均≤0.27ms |
| 公网边界 | 匿名页面302、`/api/v1/` 401 JSON、私有路径404、静态资源200、登录后六页200、检索40行、简报25份 |
| AI流水线 | 首轮`prepare_ai`排队40篇，累计完成80次中文标题/简介生成，当日用量约5.2万token（上限20万） |
| 部署检查 | `check --deploy` 仅剩W005/W008/W021：HSTS子域与preload不启用（同主机还有其他服务），HTTP→HTTPS跳转由宝塔Nginx负责 |

旧仓库 `/opt/trendradar` 与其三个systemd单元已在离机备份校验、域名切换和公网验证通过后删除；离机快照保留在 `C:\Users\ASUS\Documents\News\TrendRadar`（源码）与 `.local/legacy-final.tar.gz`（旧输出与配置）。

### 上线后修复：304被误判为失败

首轮切换后第二轮采集出现25次 `KeyError`（http=0）——httpx 的 `response.is_redirect` 对**所有** 3xx 都为真，携带 `If-None-Match` 的第二次请求收到 `304 Not Modified` 时被当成跳转，读取不存在的 `location` 抛错。后果是条件请求全部失败（当时104次请求中27次失败）并触发来源退避。

修复：只在 `301/302/303/307/308` 且存在 `Location` 时跟随跳转（见 `app/news/crawler.py` 的 `fetch`），并新增 `tests/test_fetch.py` 覆盖304、正常跳转、缺 Location、跳转环、超限响应体。已有 `CrawlRun` 失败记录保留为真实历史，未做改写。若日后再看到 `failed:0` + `KeyError`，优先检查这里。
