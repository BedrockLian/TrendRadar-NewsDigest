# TrendRadar 新闻工作台：架构、工作流与跨平台部署交接

## 1. 文档用途

本文是当前工作区的工程交接入口。后续 Agent 接手时，应先阅读本文，再查看实时状态、配置和测试。本文覆盖：

- 新闻工作台的产品行为；
- 采集、简报、网页、归档和发布的数据流；
- Windows、普通 Linux、Docker、校园服务器的运行方式；
- 私有运行数据与公开静态文件的边界；
- 发布锁、原子切换、回滚和验证；
- 当前已经验证的内容与仍需现场确认的内容。

GitHub Actions 不在当前支持范围内。`.github/workflows/crawler.yml` 保持仓库原状，仅保留手动入口，不应把它当作本项目的采集、状态持久化或线上发布保障。

## 2. 仓库和生产环境

| 项目 | 当前值 |
| --- | --- |
| 本地工作区 | `C:\Users\ASUS\Documents\News\TrendRadar` |
| 当前开发分支 | `master` |
| 推送远端 | `fork` → `https://github.com/BedrockLian/TrendRadar-NewsDigest.git` |
| 上游远端 | `origin` → `https://github.com/sansan0/TrendRadar.git` |
| 生产主机 SSH 别名 | `campus-server` |
| 生产目录 | `/opt/trendradar` |
| 生产网址 | `https://news.blian117.dpdns.org` |
| 生产运行用户 | `trendradar:trendradar` |
| 生产时区 | `Asia/Shanghai` |
| 生产调度 | systemd timer，每小时 `:00`、`:30` 运行 |
| 生产版本标记 | `/opt/trendradar/.deployed-commit` |

生产目录不是 Git 工作树。服务器代码由本地已提交版本生成 Git archive，再解压部署；不要在服务器上使用 `git pull` 判断或更新版本。

## 3. 用户看到的产品行为

首页是个人新闻编辑台，不是营销页。首屏优先显示最近一次已经完成的简报，并始终保留该简报，直到下一期真正生成。

### 3.1 固定简报

- 每天 `08:00`：早间新闻简报；
- 每天 `12:30`：午间新闻简报；
- 每天 `20:00`：晚间新闻简报；
- 每期最多 20 篇；
- 同一来源默认最多 2 篇，名额不足时允许跨板块补齐；
- URL、标题和近似标题会去重；
- 已生成简报写入 `output/briefings/**/*.md`；
- 首页提供当前简报的板块筛选和 Markdown 下载入口；
- 周日晚间可生成周报。

板块和配额由 `config/config.yaml` 的 `digest.categories` 控制，目前包括：

| 板块 | 配额 |
| --- | ---: |
| 科技与 AI | 6 |
| 游戏 | 4 |
| 社会与文化 | 4 |
| 中国、经济与国际关系 | 3 |
| 全球政治与公共事务 | 2 |
| 日本与韩国 | 1 |

### 3.2 突发与简报后更新

- 强关键词命中的突发最多显示 3 条；
- 突发有效窗口默认 180 分钟；
- 简报生成之后首次发现或内容变化的新闻进入“简报后更新”；
- 旧新闻不会因为页面刷新而重新标为更新；
- 突发投递状态和去重状态保存在 `output/briefings/.state.json`。

### 3.3 全部新闻

采集层保留所有当前 RSS 项目，首页“全部新闻”支持：

- 关键词搜索；
- 板块筛选；
- 来源筛选；
- 最新/最早排序；
- 多条件组合；
- 每次加载 40 条；
- 筛选和主题偏好保存在浏览器 `localStorage`。

浏览器只接收白名单化后的公开字段。链接必须是有效的 `http` 或 `https` URL，动态文字通过 `textContent` 写入，内嵌 JSON 会转义 `</script>`、`&`、U+2028 和 U+2029。

## 4. 技术结构

### 4.1 主数据流

```text
systemd timer / Docker supercronic / 手动命令
                     │
                     ▼
       deployment.run_once（整轮运行锁）
                     │
                     ▼
            python -m trendradar
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   RSS/热榜采集   DigestEngine   通知渠道/AI
        │            │
        ▼            ▼
 output/rss      output/briefings
 output/news     .state.json + Markdown
        └────────────┬────────────┘
                     ▼
             HomepageSnapshot
                     ▼
       trendradar.report.html 渲染
                     ▼
              output/index.html
                     │
                     ▼
 deployment.publish_static（发布锁）
                     │
                     ▼
    public/index.html + public/briefings/**
                     │
                     ▼
          Nginx / Python http.server
```

### 4.2 关键代码

| 文件 | 责任 |
| --- | --- |
| `trendradar/__main__.py` | 主流程；采集后创建 `DigestEngine`、`HomepageSnapshot`，生成 HTML，并在通知成功后记录投递 |
| `trendradar/context.py` | 把首页快照传给报告生成链路；即使当前抓取为空也保留最近简报 |
| `trendradar/core/scheduler.py` | 解析三时段配置，计算 08:00/12:30/20:00 状态和下一次推送 |
| `trendradar/digest/engine.py` | 观察文章、去重、分类、选稿、突发判断、简报状态、Markdown 存档和公开快照 |
| `trendradar/report/html.py` | 无前端框架、无 CDN 的首页 HTML/CSS/JS；服务端渲染简报，客户端处理更新和全部新闻 |
| `trendradar/report/archive.py` | 扫描 Markdown，生成 `briefings/index.html` 归档页；主程序与发布器共用 |
| `deployment/build_briefing_index.py` | 归档索引生成器的兼容命令入口 |
| `deployment/run_once.py` | 用整轮运行锁串行化“采集 → 生成 → 发布” |
| `deployment/publish_static.py` | 构建公开文件白名单、生成归档索引、整体切换公开目录 |
| `deployment/run.sh` | 校园服务器 systemd 的单次入口 |
| `deployment/trendradar-collect.service` | systemd oneshot、权限限制和资源限制 |
| `deployment/trendradar-collect.timer` | 每 30 分钟唤醒一次 |
| `docker/entrypoint.sh` | Docker once/cron 启动流程 |
| `docker/manage.py` | Docker 内手动运行、状态和静态服务器管理 |

### 4.3 DigestEngine 状态

`output/briefings/.state.json` 是 30 天滚动运行账本，主要包含：

- `articles`：标准化 URL、标题、来源、摘要、首次/最近发现时间、更新时间、分类、突发状态、所属简报；
- `results`：简报或突发结果 ID、生成时间、文章 ID、存档路径、投递时间；
- `weekly`：已生成周报，防止重复。

这个文件必须随 `output` 持久化。丢失它会丢失精确的历史发现时间、投递记录和最近简报引用。它是运行数据，不得复制到公开目录。

## 5. 私有输出与公开输出

### 5.1 私有 `output`

`output` 是应用写目录，可能包含：

```text
output/
├── index.html
├── briefings/
│   ├── .state.json
│   ├── YYYY-MM/*.md
│   ├── alerts/*.md
│   └── weekly/*.md
├── news/*.db
├── rss/*.db
├── html/**
├── txt/**
└── 其他采集快照
```

不要让 Nginx、`http.server` 或容器端口直接指向 `output`。

### 5.2 公开 `public`

发布器每次从空的唯一临时目录构建完整站点，允许出现的文件只有：

```text
public/
├── index.html
└── briefings/
    ├── index.html
    └── **/*.md
```

发布器不会复制数据库、`.state.json`、抓取快照、日志或符号链接。它会整体替换旧 `public`，因此旧版本遗留的私有文件也会被清除。

`output` 与 `public` 必须是两个互不包含的独立目录树；发布器会拒绝相同路径、父子路径和文件系统根目录，防止错误参数覆盖项目或私有输出。

## 6. 并发、原子发布和失败行为

### 6.1 两层锁

`deployment.run_once` 在项目根目录创建 `.output.run.lock`，覆盖完整的采集与发布过程。手动运行和定时运行重叠时，只允许一轮修改共享 `output`。

运行前它会暂存旧 `output/index.html`；只有子进程以 0 退出且本轮生成了新的非空首页，才进入发布。采集失败或没有生成新首页时会恢复旧输出并保持线上 `public` 不动，避免把陈旧页面误报为新版本。主程序的普通运行错误会返回非零退出码。

`deployment.publish_static` 使用 `.public.publish.lock`，防止两个独立发布动作互相删除临时目录。锁在 Windows 使用 `msvcrt.locking`，在 POSIX 使用 `fcntl.flock`；进程退出后操作系统释放锁。

默认等锁时间为 60 秒，超时会明确失败，不会并发写入。

### 6.2 完整站点切换

发布过程：

1. 检查 `output/index.html` 存在且非空；
2. 在 `public` 同级创建唯一临时目录；
3. 只复制非符号链接的 Markdown；
4. 在临时目录生成归档首页；
5. 复制首页；
6. 整体切换临时目录与 `public`；
7. 删除旧版本。

Linux 使用 `renameat2(..., RENAME_EXCHANGE)` 一次交换新旧目录，网页根路径没有中间缺失窗口。当前校园服务器的 Linux 6.6 内核和文件系统已经实际验证支持该操作。

Windows 或不支持 `RENAME_EXCHANGE` 的文件系统使用“旧目录移到唯一备份 → 新目录就位”的回退流程；普通异常会自动把备份移回。Windows 回退不是抗断电的内核级原子交换，开发机发布时不要强制终止进程。

Docker 的 `http.server` 从 `/app` 启动，并通过 `--directory /app/public` 指定根目录。这样整体替换 `/app/public` 后，服务会在下一次请求解析新路径，不会停留在已删除的旧工作目录。

## 7. 跨平台运行与部署

### 7.1 Windows 本地开发

要求：Python 3.12、`uv`。

```powershell
cd C:\Users\ASUS\Documents\News\TrendRadar
uv sync --frozen
$env:PYTHONIOENCODING = 'utf-8'
uv run --frozen python -m deployment.run_once output public
uv run --frozen python -m http.server 8080 --bind 127.0.0.1 --directory public
```

浏览器访问 `http://127.0.0.1:8080/`。Windows 终端若使用旧 GBK 代码页，包含 emoji 的日志可能触发编码错误；设置 `PYTHONIOENCODING=utf-8` 即可，数据处理本身不受影响。

直接执行 `uv run --frozen python -m trendradar` 时，程序会同步生成 `output/briefings/index.html` 并打开 `output/index.html`；首页与归档页使用相对站内链接，因此 `file://` 本地打开和 HTTP 托管都能导航。`deployment.run_once`、systemd 和 Docker 会设置受管运行标记，禁止后台任务弹出浏览器。

只需重新发布已有输出时：

```powershell
uv run --frozen python -m deployment.publish_static output public
```

### 7.2 普通 Linux

```sh
cd /path/to/TrendRadar
uv sync --frozen
PYTHONIOENCODING=utf-8 uv run --frozen python -m deployment.run_once output public
uv run --frozen python -m http.server 8080 --bind 127.0.0.1 --directory public
```

若用 Nginx/Caddy，Web 根目录必须是绝对路径下的 `public`，不能是 `output`。`output` 和项目根目录需要对运行用户可写，配置文件应按需只读。

### 7.3 Docker Compose

要包含本工作区改动，应使用源码构建文件：

```sh
docker compose -f docker/docker-compose-build.yml up -d --build trendradar
```

`docker/docker-compose.yml` 使用上游预构建镜像；只有镜像发布包含当前提交后，才能获得同样行为。

容器约定：

- `/app/config`：宿主机只读挂载；
- `/app/output`：宿主机持久化挂载，保存数据库、状态和存档；
- `/app/public`：容器内部安全发布目录，可由持久化 `output` 在启动时重建；
- 默认每 30 分钟运行；
- 默认只绑定宿主机 `127.0.0.1:8080`。

运行模式：

```text
RUN_MODE=once  -> 执行一次 deployment.run_once 后退出
RUN_MODE=cron  -> 可选立即执行，然后由 supercronic 定时执行
```

常用命令：

```sh
docker exec trendradar python manage.py run
docker exec trendradar python manage.py status
docker exec trendradar python manage.py webserver_status
docker logs --tail 200 trendradar
```

手动 `manage.py run` 与 cron 使用同一个 `.output.run.lock`，不会并发修改输出。

### 7.4 校园服务器（生产）

生产使用 systemd，不使用 Docker：

```text
trendradar-collect.timer
  └── trendradar-collect.service
        └── /bin/sh /opt/trendradar/deployment/run.sh
              └── .venv/bin/python -m deployment.run_once output public
```

服务的关键限制：

- `Type=oneshot`；
- `TimeoutStartSec=900`；
- `CPUQuota=50%`；
- `MemoryMax=600M`；
- `NoNewPrivileges=true`；
- `ProtectSystem=strict`；
- 仅 `/opt/trendradar` 可写。

环境变量位于 `/opt/trendradar/config/news-digest.env`，不要把值写进仓库或交接文档。Nginx 应把 `https://news.blian117.dpdns.org/` 指向 `/opt/trendradar/public`。

## 8. 生产发布工作流

### 8.1 发布前

1. 查看 `git status --short`，只暂存源代码、测试和文档；
2. 不要暂存 `output/**`、`__pycache__/**` 或本地 UI fixture；
3. 运行第 9 节验证；
4. 提交并推送到 `fork/master`；
5. 用已提交的精确 commit 生成 archive，避免把未跟踪运行数据带上服务器。

示例：

```powershell
$commit = git rev-parse HEAD
git archive --format=tar --prefix=trendradar/ -o "$env:TEMP\trendradar-$commit.tar" $commit
Get-FileHash -Algorithm SHA256 "$env:TEMP\trendradar-$commit.tar"
scp "$env:TEMP\trendradar-$commit.tar" campus-server:/tmp/
```

### 8.2 服务器预检

在 `/tmp` 下创建独立预检目录，解压 archive，并使用生产虚拟环境运行测试。不要先覆盖 `/opt/trendradar`。

需要确认：

- archive 本地与远端 SHA-256 一致；
- 预检目录中的测试通过；
- Python 文件可编译；
- `deployment/run.sh` 语法正确；
- `publish_static` 能在临时目录构建且不复制 `.state.json`；
- Linux 原子目录交换返回成功。

### 8.3 应用发布

发布时应短暂停止 timer，避免解压期间启动新任务；如果 oneshot 正在运行，先等待或安全停止。发布必须保留：

- `/opt/trendradar/.venv`；
- `/opt/trendradar/python`（`.venv/bin/python` 指向这里的自带 Python 运行时）；
- `/opt/trendradar/config`；
- `/opt/trendradar/output`；
- `/opt/trendradar/public`，直到新代码完成一次成功发布。

替换源码后：

```sh
sudo chown -R trendradar:trendradar /opt/trendradar
sudo install -m 0644 /opt/trendradar/deployment/trendradar-collect.service /etc/systemd/system/
sudo install -m 0644 /opt/trendradar/deployment/trendradar-collect.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trendradar-collect.timer
sudo systemctl start trendradar-collect.service
```

成功后把完整 commit 写入 `/opt/trendradar/.deployed-commit`。若使用 `rsync --delete`，必须同时排除 `.venv/`、`python/`、`config/`、`output/` 和 `public/`。若采集或发布失败，恢复发布前源码备份；保留 `output`，否则会丢失简报和投递状态。

## 9. 验证清单

### 9.1 自动验证

```powershell
$env:PYTHONIOENCODING = 'utf-8'
uv run --frozen python -m unittest discover -s tests -p 'test_*.py'
uv run --frozen python -m py_compile deployment/build_briefing_index.py deployment/publish_static.py deployment/run_once.py docker/manage.py trendradar/__main__.py trendradar/context.py trendradar/core/scheduler.py trendradar/digest/engine.py trendradar/report/archive.py trendradar/report/html.py
git diff --check
```

Shell 语法可用 Git for Windows 验证：

```powershell
& 'C:\Program Files\Git\usr\bin\sh.exe' -n deployment/run.sh docker/entrypoint.sh
```

### 9.2 公共目录安全验证

发布后，递归文件列表只能匹配：

```text
index.html
briefings/index.html
briefings/**/*.md
```

线上必须返回：

```text
GET /                                  200
GET /briefings/                        200
GET /briefings/<实际简报>.md           200
GET /briefings/.state.json             404
GET /rss/<任意数据库>.db               404
```

### 9.3 浏览器验证

至少检查：

- 桌面 `1440×900`；
- 中等宽度 `1024×768`；
- 手机 `390×844`；
- 页面无横向溢出、遮挡、断裂资源或控制台错误；
- 最近简报首条新闻在首屏可见；
- 超长标题正常换行；
- 加载更多从 40 增到 80；
- 来源、搜索、板块和排序可以组合；
- 深浅主题刷新后保留；
- `/briefings/` 能打开，Markdown 下载能访问。

### 9.4 生产状态

```sh
ssh campus-server 'cat /opt/trendradar/.deployed-commit'
ssh campus-server 'systemctl status trendradar-collect.timer --no-pager'
ssh campus-server 'systemctl status trendradar-collect.service --no-pager'
ssh campus-server 'journalctl -u trendradar-collect.service -n 200 --no-pager'
```

使用 HTTPS 请求验证页面和敏感路径，不要仅检查本地文件存在。

## 10. 本次改版的已验证证据

在提交前已完成：

- 完整单元测试通过；
- Python 编译检查通过；
- Shell 语法检查通过；
- `git diff --check` 通过；
- 真实 RSS 抓取成功：49/49 个源、961 条原始项目、886 条当前新闻；
- 本地真实输出首页包含 49 个来源，初始显示 40 条；
- 浏览器检查覆盖 `1440×900`、`1024×768`、`390×844`；
- 搜索、来源筛选、板块筛选、排序、40→80 加载、主题持久化均验证；
- 页面无横向溢出和控制台错误；
- 发布器对真实输出只生成首页、归档索引和 Markdown；
- 正在运行的 `http.server --directory` 能在整体目录切换后立即提供新版本；
- 私有 `.state.json` 的 HTTP 请求返回 404；
- 校园服务器 Linux 6.6 上 `RENAME_EXCHANGE` 已做临时目录实测。

Docker CLI 在当前 Windows 开发机不可用，因此本地没有执行完整镜像构建。Dockerfile、entrypoint、管理命令、Shell 语法和共享发布模块已经验证；发布前若目标环境依赖 Docker，应在有 Docker daemon 的机器补跑源码镜像构建和容器级 HTTP 检查。

## 11. 故障定位

### 首页仍是旧版

1. 查看 `.deployed-commit` 是否是预期提交；
2. 查看最近一次 service 日志；
3. 对比 `output/index.html` 与 `public/index.html` 修改时间；
4. 直接运行 `deployment.publish_static`；
5. 检查 Nginx root 是否仍指向 `output` 或旧目录。

### 首页显示“首期简报正在准备”

1. 检查 `output/briefings/.state.json` 是否存在且可读；
2. 检查 `results` 中是否有 `kind: digest` 且文章 ID 仍存在；
3. 检查当前时间是否已经完成 08:00/12:30/20:00 任一期；
4. 检查简报 Markdown 是否写入；
5. 不要删除状态文件来“重置页面”。

### `/briefings/` 404

1. 检查 `public/briefings/index.html`；
2. 重新运行安全发布器；
3. 检查 Nginx 是否允许目录索引文件 `index.html`；
4. 检查网页根是否为 `/opt/trendradar/public`。

### 发布等待锁超时

1. 查看是否已有手动或定时采集正在运行；
2. 查看 service/container 日志；
3. 不要直接删除锁文件来打断仍在运行的进程；
4. 进程退出后 OS 锁会释放，锁文件本身保留不影响下一次运行。

### Windows 控制台报编码错误

设置：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
```

然后重新运行。该错误通常来自控制台打印 emoji，而不是 RSS 数据或 HTML 编码。

## 12. 后续 Agent 接手顺序

1. 读取本文件；
2. 运行 `git status --short`，区分源代码与本地生成物；
3. 读取 `/opt/trendradar/.deployed-commit` 和 systemd 状态；
4. 检查 `output/briefings/.state.json`，不要修改；
5. 运行最小相关测试，再运行完整测试；
6. 修改网页时必须同时做桌面和手机浏览器验证；
7. 修改发布路径时必须验证敏感文件 404；
8. 仅从已提交 commit 生成生产 archive；
9. 部署后手动触发一次 service，并用 HTTPS 验证首页、归档和敏感路径；
10. 更新本文件中的验证事实和新限制。

接手时最重要的约束是：`output` 是私有持久状态，`public` 是可随时重建的公开白名单；任何部署方式都必须维持这条边界。
