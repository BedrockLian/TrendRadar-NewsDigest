# TrendRadar 新闻工作台：架构、工作流与跨平台部署交接

## 1. 文档用途

本文是当前工作区的工程交接入口。后续 Agent 接手时，应先阅读本文，再查看实时状态、配置和测试。本文覆盖：

- 新闻工作台的产品行为；
- 采集、简报、网页、归档和发布的数据流；
- Windows、普通 Linux、Docker、校园服务器的运行方式；
- 私有运行数据与公开静态文件的边界；
- 发布锁、原子切换、回滚和验证；
- 当前已经验证的内容与仍需现场确认的内容。

GitHub Actions 不在当前支持范围内。`.github/workflows/crawler.yml` 已改为仅保留手动入口（`workflow_dispatch`），不再有定时触发，不应把它当作本项目的采集、状态持久化或线上发布保障。

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
| 生产调度 | systemd timer，每 30 分钟触发（每小时 `:00` 与 `:30`） |
| 生产版本标记 | `/opt/trendradar/.deployed-commit` |
| 本机运维脚本（仓库外） | `C:\Users\ASUS\Documents\News\ops\`（`precheck.sh` / `deploy.sh` / `probe_*.py`） |

生产目录不是 Git 工作树。服务器代码由本地已提交版本生成 Git archive，再解压部署；不要在服务器上使用 `git pull` 判断或更新版本。

### 2.1 SSH 连接与身份验证

以下信息于 2026-09-11 在当前 Windows 开发机和生产服务器双向核验。仓库会被推送到 GitHub，因此这里只记录连接参数、密钥位置和公开指纹，不保存私钥正文、服务器密码、API Key 或通知令牌。

| 项目 | 当前值 |
| --- | --- |
| SSH 别名 | `campus-server` |
| 地址 | `43.128.10.41` |
| 端口 | `22` |
| 登录用户 | `root` |
| 服务器主机名 | `VM-0-4-opencloudos` |
| 本机 SSH 配置 | `C:\Users\ASUS\.ssh\config` |
| 本机私钥 | `C:\Users\ASUS\.ssh\id_ed25519` |
| 本机公钥 | `C:\Users\ASUS\.ssh\id_ed25519.pub` |
| 已知主机记录 | `C:\Users\ASUS\.ssh\known_hosts` |
| 服务器授权公钥文件 | `/root/.ssh/authorized_keys` |
| 客户端公钥指纹 | `SHA256:HvKRu7LpuyrsZ8du6pL3e5vtP09wy5aWovg0CNF+LK4`（ED25519） |

当前 `C:\Users\ASUS\.ssh\config` 中与生产服务器有关的有效配置为：

```sshconfig
Host campus-server
  HostName 43.128.10.41
  Port 22
  User root
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
```

本机私钥 ACL 只授予当前 Windows 用户、`SYSTEM` 和 `Administrators` 完全控制。服务器 `authorized_keys` 中已安装的公钥指纹与本机公钥指纹一致。对应公钥全文如下；公钥不是认证秘密：

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAII1MMnGfd12g9Ob4Eji52xYGYBFMVns3AETtFQrHFEJ6 ASUS@ASUS-FX608LM
```

当前主机可以无交互执行：

```powershell
ssh -o BatchMode=yes campus-server 'whoami; hostname'
scp .\待上传文件 campus-server:/tmp/
```

首次连接或重建 `known_hosts` 时，必须核对服务器主机指纹：

| 类型 | SHA-256 指纹 |
| --- | --- |
| ED25519 | `SHA256:TtqUknO3nzVo19SaK2YdX8B82zo/5sNskeFbJqioLyk` |
| ECDSA | `SHA256:KdnQsxTTKBiLkdDH0Ts2K6ES22nO9+mb732DZLlXty0` |
| RSA | `SHA256:unywRck22+1g6ymQGSp996GDsbdbWWwYnLwUAKJvEpE` |

服务器当前允许公钥认证，`AuthorizedKeysFile` 为 `.ssh/authorized_keys`。部署命令使用密钥认证，不依赖服务器密码；当前会话以 `root` 登录，因此无需额外 sudo 密码。

其他 Agent 若运行在同一台 Windows 主机，直接使用 `ssh campus-server`，不得读取或复制私钥正文。迁移到另一台可信设备时，应通过密码管理器、加密移动介质或现有安全通道单独传送私钥，随后限制文件权限；不要通过 Git、聊天、邮件、日志或本文传递。更稳妥的做法是在新设备生成独立密钥，并通过现有连接把新公钥追加到 `/root/.ssh/authorized_keys`。完成后用上述指纹和 `BatchMode` 命令验证，再撤销不再使用的旧公钥。

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

### 3.3 首页信息架构（工作台）

首页是**工作台**：**开屏第一眼就是当天要读的简报**，运行读数整体搬到侧栏的**运行概览**页，
自上而下：

1. **数据面行**：快照时刻、最后刷新时间、待读条数，以及自动刷新 / 导出 Markdown / 刷新快照三个动作。
2. **突发条**（有命中时）。
3. **最新一期简报**：按板块分组的阅读流，组头给出「配额 N · 入选 M」；本轮无候选的板块在列表末尾
   用一行说明（名额由其他板块按引擎规则补齐）。板块筛选与 Markdown 下载入口都在这一节。
4. **本期观察**（AI 分析成功时才有）。
5. **简报后更新队列**：本期简报发布后首次出现或内容变化的条目，逐条可标记已读。
6. **全部新闻台账**：全量条目，可搜索（标题 / 摘要 / 来源 / 板块）、按板块与状态筛选、
   三种排序（发布时间 / 板块 / 来源）、每次载入 40 条、逐行标记已读、多源同题标 `×N`、
   未来发布时间的条目标 `?`。
7. **导出 Markdown**：导出的是**当前筛选下的全部条目**，不只是已载入的行；可复制或下载 `.md`。

全页只有一个 `<h1>`（本期简报标题）：顶栏已经写明「新闻工作台」，工作台不再重复一次大标题，
这也是数据面行能留在首屏最上面的原因。侧栏「最新一期」指向 `#digest`，与开屏区块一致。

**运行概览**（`/overview/`，侧栏「全部新闻」下一项）是**独立的读数页**，不再折叠在首页里：
数据面口径说明、KPI 行（台账条目 / 本期新增 / 实质更新 / 待读；待读 = 简报后更新中未标记已读的
条数）、采集节律条（每 30 分钟 · :00 / :30、下一轮采集倒计时按访客本机时间算、简报窗口与下一期
估算、新鲜度窗口）、近 7 日入库量折线（按条目**发布时间**分箱，不是采集时间；图下写明窗口外 /
无时间 / 未来时间的条数）与本轮新增与更新动态列表，最上面是唯一的实心按钮「刷新快照」。它和首页
由同一次渲染产出、读同一份 `homepage-data`，所以两边的数字不可能对不上；这一页只渲染读数，
没有台账、队列与导出。

### 3.3.1 台账表头的吸顶行为（2026-09-13 修复）

`.db-head` 是 `position: sticky`，靠 `--bar-h` 贴在顶栏下沿。它此前不生效：`.db` 上写着
`overflow: hidden`（本意是裁圆角），而 `overflow: hidden` 会让 `.db` 自己成为**滚动容器**，
于是 sticky 的参照物从页面变成了 `.db` 本身 —— 表头被恒定下推一个 `--bar-h`，正好压在头两行
数据上（线上实测：行文字被表头裁成半行，看起来像"表头显示错误"）。改成 `overflow: clip` 后圆角
照旧保留，而 clip 不创建滚动容器，表头恢复按页面吸顶。回归见 `tests/test_homepage.py` 与设计
工作区生成器里的 `assert "overflow: clip" in page_css`。

浏览器本地状态（`localStorage`）：`trendradar.read.v1`（已读）、`trendradar.auto`（自动刷新）、
`trendradar-theme` / `trendradar-sidebar-collapsed`（外观）。已读只在访客本机有效，换设备不跟随。

「新增 / 实质更新」的口径相对**最近一期简报**判定：新增 = 该期发布后首次出现（`first_seen`），
实质更新 = 同一链接的标题发生变更（`update_detected_at`，见 `engine.py` 的 `status` 判定）。
页面上的口径说明由渲染器写在数据面提示里，不靠读者猜。

当前生产配置为 52 个 RSS 源，其中科技与 AI 直接来源 8 个，另把 Rest of World 的技术报道映射到
科技板块。2026-09-12 扩源前最近 8 份简报科技栏为 `2/6/0/4/6/0/4/3`，平均 3.12 篇，只有
2 份填满 6 篇配额；现有科技源最近 24 小时虽抓到 37 条，但 27 条集中于 WIRED 和 Ars Technica，
OpenAI 官方源仅 3 条。故增加 TechCrunch 官网 Feed、The Verge、Engadget 三个高频编辑媒体，不提高
总篇数或科技配额。生产同构 canary 分别解析 20、10、20 条，全部在 48 小时内，且与现有文章池的
规范化 URL 和近似标题重合均为 0。awesome-rss-feeds 中 TechCrunch 的 FeedBurner 旧地址已串源，
VentureBeat 的 FeedBurner 超过 8 天未更新、官网 Feed 返回 429，均不使用。

浏览器只接收白名单化后的公开字段。链接必须是有效的 `http` 或 `https` URL，动态文字通过 `textContent` 写入，内嵌 JSON 会转义 `</script>`、`&`、U+2028 和 U+2029。

### 3.4 载荷拆分

首页不再把所有内容内联。`homepage-data` 只带渲染首屏必需的东西：

```json
{
  "updates": [12, 40, 41],          // 指向 allNews 的下标，不是第二份文章对象
  "allNews": [{ "title", "url", "published_at", "category_id", "status", "_si", "_ci" }],
  "categories": ["科技与 AI", ...],  // 分类名查表
  "sources": ["WIRED", ...]         // 来源名查表
}
```

- `summary` **不在** `allNews` 里，它随 `briefings-summaries.json` 首屏之后再取；页面同时内联
  一份副本作为 `file://` 打开和请求失败时的兜底，取到后重渲染一次；
- `_si` / `_ci` 是 `sources` / `categories` 的下标，客户端水合时还原成显示字符串；
- `updates` 是下标数组，避免把「简报后更新」的条目整份复制一遍。

拆分当时的实测（生产数据 876 篇）：首屏 gzip **152.9 KB → 81.6 KB**，内联载荷 raw **464.6 KB → 236.9 KB**；当前（2026-09-12，2644 篇）首页 raw 约 **422 KB**、gzip 约 **145 KB**。

### 3.5 正文翻译

启用 `AI_TRANSLATION_ENABLED` 后，`DigestEngine` 在投影前为文章补上译文，因此**简报、
简报后更新、全部新闻**三处一起中文化（详见 4.4）。译文按 `content_hash` 缓存；正常只翻译
一次，缺少标题或简介译文的条目会在后续轮次补齐。积压回填的速度由 `config/config.yaml` 的
`digest.translation` 控制（`batch_size` / `max_new_per_run` / `max_retry_calls` /
`refusal_retry_hours` / `max_pass_seconds`，默认 40 / 40 / 8 / 6 / 75）。翻译模型可由
`ai_translation.model` 独立指定，避免全局分析模型不适合批量翻译；环境变量
`AI_TRANSLATION_MODEL` 可覆盖该值。五个节奏参数对应的环境变量
`TRANSLATION_BATCH_SIZE` / `TRANSLATION_MAX_NEW_PER_RUN` /
`TRANSLATION_MAX_RETRY_CALLS` / `TRANSLATION_REFUSAL_RETRY_HOURS` /
`TRANSLATION_MAX_PASS_SECONDS` 可以覆盖文件值。

未启用、未配置 `AI_API_KEY` 或接口失败时，页面回落到原始 RSS 文本，行为与加入该功能前一致。

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
    public/index.html + public/briefings/** + *.gz
                     │
                     ▼
     deployment.serve_public（trendradar-web.service）
                     │
                     ▼
          Nginx 反代 127.0.0.1:18080
```

Docker 部署另有其路径：`http.server` 在容器内提供 `/app/public`（见 §7.3）。

### 4.2 关键代码

| 文件 | 责任 |
| --- | --- |
| `trendradar/__main__.py` | 主流程；采集后创建 `DigestEngine`、`HomepageSnapshot`，生成 HTML，并在通知成功后记录投递 |
| `trendradar/context.py` | 把首页快照传给报告生成链路；即使当前抓取为空也保留最近简报；提供 `create_translator` |
| `trendradar/core/scheduler.py` | 解析三时段配置，计算 08:00/12:30/20:00 状态和下一次推送 |
| `trendradar/digest/engine.py` | 观察文章、去重、分类、选稿、突发判断、简报状态、Markdown 存档和公开快照；持有翻译缓存并做投影本地化 |
| `trendradar/report/html.py` | 首页与运行概览的 HTML 拼装（`render_html_content(..., page=...)` 选文档）；服务端渲染简报，构建精简载荷与摘要旁车文件 |
| `trendradar/report/workspace_template.py` | 首页信息架构、页面级 CSS 与客户端运行时。由设计工作区的 `build-production-ia.py` 从定稿原型生成，**不要手改**；改法见文件头 |
| `trendradar/report/overview_template.py` | 运行概览（`/overview/`）页面体与它的运行时。与首页共用令牌、页面 CSS 和一半运行时（同一个生成器在同一节切开），**不要手改** |
| `trendradar/report/workspace_theme.py` | 公开页面唯一的主题令牌、应用外壳、侧栏、顶部栏和深浅主题/抽屉行为来源；也是字体分发的唯一来源（拉丁与数字走 CDN 的 IBM Plex，中文走系统栈，见 §10.3）。仪表盘/存档/详情三处共用它 |
| `trendradar/report/archive.py` | 扫描 Markdown，生成统一存档索引及安全 HTML 阅读页；主程序与发布器共用 |
| `trendradar/utils/url.py` | URL 规范化与公开 HTTP/HTTPS 外链校验；Digest、首页和详情解析共用 |
| `deployment/run_once.py` | 用整轮运行锁串行化“采集 → 生成 → 发布” |
| `deployment/publish_static.py` | 构建公开文件白名单、生成归档索引、写出 gzip 边车、整体切换公开目录 |
| `deployment/compress.py` | 为公开目录中的文本资产生成确定性 `.gz` 边车（发布时一次） |
| `deployment/serve_public.py` | 生产静态服务器；优先返回 `.gz` 边车，带 ETag/304 与路径穿越防护 |
| `deployment/run.sh` | 校园服务器 systemd 的单次入口 |
| `deployment/trendradar-collect.service` | systemd oneshot、权限限制和资源限制 |
| `deployment/trendradar-collect.timer` | 每 30 分钟唤醒一次 |
| `deployment/trendradar-web.service` | 静态站点服务单元（绑定 `127.0.0.1:18080`，由 Nginx 反代） |
| `docker/entrypoint.sh` | Docker once/cron 启动流程 |
| `docker/manage.py` | Docker 内手动运行、状态和静态服务器管理 |

### 4.3 DigestEngine 状态

`output/briefings/.state.json` 是 30 天滚动运行账本，主要包含：

- `articles`：标准化 URL、标题、来源、摘要、首次/最近发现时间、更新时间、分类、突发状态、所属简报；
- `results`：简报或突发结果 ID、生成时间、文章 ID、存档路径、投递时间；
- `weekly`：已生成周报，防止重复。

这个文件必须随 `output` 持久化。丢失它会丢失精确的历史发现时间、投递记录和最近简报引用。它是运行数据，不得复制到公开目录。

### 4.4 翻译缓存

`output/briefings/.translations.json` 是**独立的**滚动缓存，按 `content_hash` 索引每篇文章的
`title_zh` / `summary_zh`：

- 与 `.state.json` 分开存放是刻意的：丢失缓存只损失金钱（会重新翻译），丢失状态则损失正确性；
- 缓存条目在 `_prune_translation_cache()` 中按 `articles` 存活集合回收；
- `Engine._localized(record, field)` 在**投影时**解析译文，因此 `.state.json` 不会为每篇文章
  多存一份翻译，既有状态文件也不需要迁移；
- 关掉 `AI_TRANSLATION_ENABLED` 后引擎行为与加入翻译功能前完全一致。

单次运行的翻译量上限由 `config/config.yaml` 的 `digest.translation` 控制，避免积压时出现意外账单：

| 键 | 默认 | 含义 |
| --- | ---: | --- |
| `batch_size` | 40 | 每次请求提交的记录数（标题 + 摘要 = 2 倍文本条数） |
| `max_new_per_run` | 40 | 单轮最多为多少条新记录付费 |
| `max_retry_calls` | 8 | 被内容风控拒绝后允许的额外重试与切分调用次数 |
| `refusal_retry_hours` | 6 | 被拒条目多少小时后重新尝试 |
| `max_pass_seconds` | 75 | 单轮回填的墙钟上限；到点收工，剩余下轮继续 |

环境变量 `TRANSLATION_BATCH_SIZE` / `TRANSLATION_MAX_NEW_PER_RUN` /
`TRANSLATION_MAX_RETRY_CALLS` / `TRANSLATION_REFUSAL_RETRY_HOURS` /
`TRANSLATION_MAX_PASS_SECONDS` 优先于文件值。这些值经 `_load_digest_config()` 进入引擎的
`TRANSLATION` 段。

翻译器默认复用 `ai.model`，但 `ai_translation.model` 可单独覆盖；生产环境也可用
`AI_TRANSLATION_MODEL` 覆盖文件值。2026-09-12 生产同批 40 篇（80 段、6930 字符）探针显示：
有效生产模型 `deepseek/deepseek-flash` 连续三次均返回空响应（`parsed=0`、`raw_chars=0`，
每次 23～24 秒），而 `deepseek/deepseek-chat` 连续三次均为 `80/80`、9.1～10.1 秒。因此正文翻译固定使用
`deepseek/deepseek-chat`，其他 AI 功能仍可继续使用全局模型。

2026-09-12 生产运行态核对：全局 `AI_MODEL=deepseek/deepseek-flash`（环境变量），正文翻译
`ai_translation.model=deepseek/deepseek-chat`（YAML，环境变量未覆盖），节奏 40/40/8/6/75，与仓库
`config/config.yaml` 完全一致。

**语言判断不能把“含汉字”直接等同于中文。** 日文标题常同时含汉字和假名；旧实现只要看到
`\u4e00-\u9fff` 就判定无需翻译，导致 NHK 的日文标题和简介被原样写入翻译缓存。现在平假名与
韩文字符优先判为待翻译；片假名仅在其数量超过汉字、或全文没有汉字时判为待翻译，以允许中文
译文保留「イコールアース」等日文专名。

**缓存按字段判断完整，回填优先最新文章。** 旧实现只检查 `content_hash` 是否存在于缓存，
`title_zh` 为空、或缓存值仍是日文，也会让整篇永久跳过。现在标题和简介分别验收，不合格字段会
重新翻译。普通回填按 `first_seen` 从新到旧处理；否则状态字典的旧→新插入顺序会让当天标题排在
一千多条历史积压之后。已经生成的当期简报在后续采集时也会补译标题，再生成中文简介，避免出现
“英文标题 + 中文简介”的混合状态。

**时间才是要卡住的量。** 供应商会成段拒绝：2026-09-11 23:30 那轮 10 次调用耗时 221 秒、
只落地 28/40 条，整轮 5 分 22 秒（当时只有调用次数上限）。因此 `_translate_texts()` 在每次
调用前检查墙钟截止时间（`max_pass_seconds`，默认 75 秒），到点就结束本轮回填、剩余记录留给
下一轮；日志行会附上「（到点收工，剩余下轮继续）」。这一条与「调用次数上限」互为兜底：
次数上限防递归膨胀，时间上限防成段拒绝。

**拒绝要先重试、不要立刻切分。** 生产实测：供应商对同一批内容的拒绝是**偶发**的——
20 条文本被拒后 2 秒，包含同样内容的 40 条文本请求就翻译成功了。所以 `_translate_texts()`
先原样重发一次，只有仍被拒才二分切分去隔离"有毒"条目。此前一被拒就切分，把整份额度
（10 次调用、2 分 20 秒）花在隔离一个根本不是问题源的条目上。

**拒绝是延期，不是判决。** `.translations.json` 的 `refused` 记录拒绝时间戳，
`_refusal_is_fresh()` 只在窗口内（默认 6 小时）跳过；过期即重试，翻译成功后清除该记录。
否则一次偶发拒绝会让那条新闻永远停在英文。

**AI 简介同样有额度上限。** `_ai_summaries_for()` 的切分也是递归的，由
`digest.ai_summaries.max_calls`（默认 8，环境变量 `AI_SUMMARIES_MAX_CALLS`）限制单次简报的
调用总数；额度用尽时剩余条目保留规则摘要，不会拖住整轮。

每轮回填会打印一行汇总，便于直接看到节奏（此前这一步在日志里是完全静默的）：

```text
[简报] 翻译回填: 40/40 条入库, 1 次调用, 9.5s
```

**单轮内的 AI 调用预算是按「本轮实际排队的记录数」算的，不是按整池。** 每轮采集会把整份
在册文章（当前约 2600 条）交给引擎，若按池算就会授权约 100 次调用。旧实现正是这样：一次被风控
拒绝的批次会递归对半切分，外加 48 次重试额度，把单轮翻译拖到 8~9 分钟（实测调用约 3~9 秒/
次，2026-09-11 23:00 那轮采集总耗时 9 分 46 秒，其中 8 分 21 秒花在这一步，systemd 的硬超时
是 900 秒）。现在单轮上限为「排队批次数 + 8」次调用，正常情况下就是 1 次调用、约 10 秒。

### 4.5 选稿配额

`config/config.yaml` 的 `digest.categories[].quota` 是**总量**而非增量，`_select()` 分四轮：

1. **预配额轮** — 突发与「更新」条目优先。非突发更新最多占一半席位，且任何板块在此轮都不得
   超过自身配额（突发不受限）。`status: updated` 是**粘性标记**，池中很容易多过整期容量，
   不设这两道闸门会让后面的配额轮完全执行不到。
2. **配额轮** — 各板块按 `current >= quota` 精确填充；`current` 计入预配额轮已占席位。
3. **借调轮** — 用剩余席位按分数补齐，沿用 `source_limit` 保持来源多样性。
4. **兜底轮** — 若仅因 `source_limit` 无法凑满 `max_items`，放宽来源限制补齐。

`source_limit` 是多样性目标而非绝对约束：当某板块的候选几乎全来自一个高频源时（例如
`tech_ai` 的 24 条候选里 22 条来自 WIRED），严格按上限会让「配额 6」变成「实际 0」。因此
**在填充本板块保留份额时允许超出该上限**，被放宽的源会记入 `relaxed_sources`，后续借调轮
仍视其为已耗尽。

## 5. 私有输出与公开输出

### 5.1 私有 `output`

`output` 是应用写目录，可能包含：

```text
output/
├── index.html
├── briefings-summaries.json      ← 首页摘要旁车（会发布）
├── briefings/
│   ├── .state.json
│   ├── .translations.json        ← 翻译缓存（只有 AI 翻译启用时存在）
│   ├── YYYY-MM/*.md
│   ├── alerts/*.md
│   └── weekly/*.md
├── news/*.db
├── rss/*.db
├── html/**
├── txt/**
└── 其他采集快照
```

不要让 Nginx、`serve_public` 或容器端口直接指向 `output`。

### 5.2 公开 `public`

发布器每次从空的唯一临时目录构建完整站点。**源文件**白名单只有：

```text
public/
├── index.html
├── briefings-summaries.json      ← 按文件名精确放行，可选
├── overview/
│   └── index.html                ← 运行概览（与首页同一次渲染产出）
└── briefings/
    ├── index.html                ← 发布器生成
    ├── **/*.html                 ← 发布器由受控 Markdown 生成的阅读页
    └── **/*.md                   ← 原始简报下载
```

除这些源文件外，发布器还会为每个文本资产生成确定性的 `<name>.gz` 边车，因此实际发布结果形如：

```text
public/
├── index.html
├── index.html.gz
├── briefings-summaries.json
├── briefings-summaries.json.gz
├── overview/
│   ├── index.html
│   └── index.html.gz
└── briefings/
    ├── index.html
    ├── index.html.gz
    ├── **/*.html  +  **/*.html.gz
    └── **/*.md    +  **/*.md.gz
```

`.gz` 是**已公开内容**的派生表示，不是新的信息面；发布器的**源白名单**没有放宽，所以
`.state.json`、`.translations.json`、数据库、抓取快照、日志和符号链接依旧不会被复制，
它们的 `.gz` 自然也不会出现。第 9.2 节的目录校验已相应更新。

发布器会整体替换旧 `public`，因此旧版本遗留的私有文件（含其边车）也会被清除。

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

要求：Python ≥3.12（`pyproject.toml`）、`uv`。本机 `.venv` 当前为 Python 3.14.5，生产 `.venv` 为 3.12.14。

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

- `Type=oneshot`、`Nice=10`；
- `TimeoutStartSec=900`；
- `CPUQuota=50%`、`MemoryMax=600M`；
- `NoNewPrivileges=true`、`PrivateTmp=true`、`ProtectHome=true`；
- `ProtectSystem=strict`，`ReadWritePaths=/opt/trendradar`（仅该目录可写）。

环境变量位于 `/opt/trendradar/config/news-digest.env`，不要把值写进仓库或交接文档。该文件应由 `trendradar:trendradar` 持有并设为 `0640`。

> **写入该文件的坑**：`AI_API_BASE=` 这一行在文件末尾，**没有结尾换行符**。用
> `printf '...\n' >> file` 追加会把新键**粘到 `AI_API_BASE=` 的值上**，产生类似
> `AI_API_BASE=AI_TRANSLATION_ENABLED=true` 的结果，systemd 会把整个字符串当成 API base，
> 而该键本身消失。追加后务必用 `awk -F= '{print $1" len="length($2)}'` 核对，或干脆整份重写
> 文件（用 `install -m 0640 -o trendradar -g trendradar` 落地）。systemd 的 `EnvironmentFile`
> 会剥掉行尾 `\r`，所以 CRLF 本身不是问题；但混用 CRLF/LF 会让 `sed -i` 的 `^` 锚点失配。

AI 简介使用 `AI_API_KEY`、`AI_MODEL`，兼容接口按需增加 `AI_API_BASE`。没有密钥或接口失败时，简报和统计周报仍使用 RSS 摘要生成。通知复用项目现有环境变量，例如 `FEISHU_WEBHOOK_URL`、`DINGTALK_WEBHOOK_URL`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID` 和邮件变量；未配置渠道时只采集并生成网页与 Markdown。

启用工作台正文翻译需同时设置 `AI_TRANSLATION_ENABLED=true`。目标语言由
`AI_TRANSLATION_LANGUAGE` 覆盖 `config.yaml` 的 `ai_translation.language`；翻译模型由
`AI_TRANSLATION_MODEL` 覆盖 `ai_translation.model`。未单独指定模型时才回退到共享的
`AI_MODEL` / `ai.model`。

### 7.5 生产访问链路（实测）

交接文档早期版本写的「Nginx 把站点指向 `/opt/trendradar/public`」**与实际不符**。真实链路是：

```text
浏览器
  └── Nginx（宝塔，/www/server/nginx，监听 443，HTTP/3 已开）
        └── location ^~ /  →  proxy_pass http://127.0.0.1:18080/
              └── systemd: trendradar-web.service
                    └── python -m deployment.serve_public
                          --directory /opt/trendradar/public --port 18080 --bind 127.0.0.1
```

要点：

- Nginx **不直接读**站点根。宝塔面板里的站点根 `/www/wwwroot/news.blian117.dpdns.org/`
  只有一个 917 字节的占位 `index.html`（2026-09-08 遗留），**发布器从不写它**；
- `serve_public` 优先返回发布时生成的 `.gz` 边车。此前的 `python -m http.server` 完全没有
  `Content-Encoding` 支持，导致 Nginx 必须**对每个请求**现场压缩约 530 KB 的首页；
- `trendradar-web.service` 绑定 `127.0.0.1`（Nginx 走环回），因此 18080 不对外暴露；
- 代理块对所有非静态后缀强制 `Cache-Control: no-cache`。这是合理的（首页每轮都变），
  但意味着每次访问都会回源；预压缩把这部分成本压到最低。

改动该链路（换服务器、换端口、换反代）时必须同时更新 `deployment/trendradar-web.service`。

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

当前用仓库外的 `C:\Users\ASUS\Documents\News\ops\precheck.sh`（传到服务器后 `sh /tmp/precheck.sh <commit>`）自动完成本节检查：解压 archive、用生产 venv 跑全部单元测试、`py_compile`、`sh -n deployment/run.sh`、在样例目录验证 `publish_static` 白名单（`.state.json` / `.translations.json` 及其 `.gz` 不得泄漏）、验证 `serve_public` 的 gzip 与敏感路径 404、验证 `RENAME_EXCHANGE`；全部通过后输出 `PRECHECK: PASS`。

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

当前用仓库外的 `C:\Users\ASUS\Documents\News\ops\deploy.sh`（`sh /tmp/deploy.sh <commit>`）自动执行发布：停止 timer 并等待在跑的轮次结束；把现有源码备份到 `/opt/trendradar-src-backup-<时间戳>`；只替换 `trendradar/ deployment/ docker/ tests/ docs/ mcp_server/`、`config/*.yaml` 与顶层 `*.py` / `*.toml` / `version`；安装 systemd 单元并 `daemon-reload`；写入 `.deployed-commit`；重启 `trendradar-web.service`；重新启用 timer。下面的手工命令是它的等价步骤。

> **`deploy.sh` 会用归档里的 `config/*.yaml` 覆盖生产同名配置**，因此配置改动必须走仓库提交，不要在服务器上直接改 YAML；运行环境变量在 `config/news-digest.env`，不受覆盖影响。

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
uv run --frozen python -m py_compile deployment/compress.py deployment/serve_public.py deployment/publish_static.py deployment/run_once.py docker/manage.py trendradar/__main__.py trendradar/context.py trendradar/core/scheduler.py trendradar/digest/engine.py trendradar/report/archive.py trendradar/report/generator.py trendradar/report/html.py trendradar/report/workspace_template.py trendradar/report/workspace_theme.py
git diff --check
```

Shell 语法可用 Git for Windows 验证：

```powershell
& 'C:\Program Files\Git\usr\bin\sh.exe' -n deployment/run.sh docker/entrypoint.sh
```

以上命令与服务器 `ops/precheck.sh` 等价（后者还会验证发布白名单、`serve_public` 与 `RENAME_EXCHANGE`）；`unittest discover` 当前为 **124** 个用例（其中 11 个专门钉住首页信息架构：区域存在性、**开屏顺序与折叠块**、模板标记清零、台账表头与行模板列数一致、载荷的新鲜度字段、板块下标重映射、简报分组与配额、数据面口径文案、节律文案与 `deployment/trendradar-collect.timer` 及 `config/config.yaml` 一致、调色板/强调色/字体栈纪律）。

### 9.2 公共目录安全验证

发布后，递归文件列表只能匹配（每一条都允许出现对应的 `.gz` 边车）：

```text
index.html
briefings-summaries.json
briefings/index.html
briefings/**/*.html
briefings/**/*.md
```

也就是说，任何**不以 `.gz` 结尾**的文件都必须匹配上述四条之一；`.gz` 文件必须恰好是某个
匹配文件的 `<name>.gz`。不允许出现 `.state.json`、`.translations.json`、数据库或快照，
自然也不允许出现它们的 `.gz`。

线上必须返回：

```text
GET /                                  200
GET /briefings/                        200
GET /briefings/<实际简报>.html         200
GET /briefings/<实际简报>.md           200
GET /briefings-summaries.json          200
GET /briefings/.state.json             404
GET /briefings/.state.json.gz          404
GET /rss/<任意数据库>.db               404
GET /.state.json                       404
```

同时确认预压缩生效：带 `Accept-Encoding: gzip` 的请求返回 `Content-Encoding: gzip`，
`Content-Type` 描述**解码后**的表示（首页为 `text/html`，而不是 `application/gzip`）。

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

## 10. 历史发布记录

### 10.1 2026-09-08 初版发布

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

### 10.2 2026-09-12 后续发布（翻译与来源）

- 正文翻译使用独立稳定模型 `deepseek/deepseek-chat`（`ai_translation.model`），不再受全局 `AI_MODEL` 影响；
- 标题本地化修复：日文按假名/韩文优先判外文，翻译缓存按字段校验完整性，回填按 `first_seen` 从新到旧，已生成的当期简报在后续采集时补译标题；
- RSS 扩源至 52：新增 TechCrunch（官网 Feed）、The Verge、Engadget；生产 canary 分别解析 20 / 10 / 20 条，48 小时内有更新，且与存量文章零重合；
- 部署后连续三轮实测：51/52、52/52、51/52 个源抓取成功，每轮 974～999 条，翻译均 40/40（8.3～9.1 秒），整轮约 3.5 分钟；
- 全量单元测试 112 个用例通过；生产 `config/config.yaml` 与仓库完全一致。

### 10.3 2026-09-12 第二次发布（字体分发）

- commit `c9df505eb7ffbd40148bd757c2fd085a7143081f`，只改 `trendradar/report/workspace_theme.py`；
- 去掉第三方 `@fontsource-variable/inter@5.2.8` 样式表，改为 Fontsource IBM Plex（OFL 1.1）：拉丁与数字 7 个字重（sans 400/500/600/700 + mono 400/600/700），每个字重一条 `@font-face`、两条同序 `src`（主源 `registry.npmmirror.com`、备源 `cdn.jsdelivr.net`），`unicode-range` 限定拉丁区段；7 个文件实测合计 135.8 KB；
- 中文不下载任何字体：`--font-ui` 尾部保留雅黑/苹方/Noto 兜底；`--font-mono` 以 CJK 无衬线兜底收尾，不再以 generic `monospace` 结尾（中文 Windows 上 Chrome 会把 generic monospace 解析成宋体，数字会渲染成衬线字形）；
- 工作台、简报存档、简报详情三处共用 `HEAD_ASSETS` / `THEME_CSS`，因此一次覆盖全部公开 HTML 页面；
- 部署前：全量单元测试 113 个用例通过（本地与生产 venv 各一次）、`py_compile` 通过、`precheck.sh` 输出 `PRECHECK: PASS`；archive 两端 sha256 一致（`49da0ca6b8a0772785761eada29edeec88b61cf48493c52a7dda6a0d653782a7`）；
- 部署后：用生产源码在 `/tmp` 渲染简报存档 14 个页面逐项核对 —— 7 条 `@font-face`、逐条双源降级、逐条 `unicode-range`、无 Inter 引用、两个字体令牌已换；线上 `public/index.html` 在下一轮采集时按新模板重新生成（静态生成的固有行为）；
- 中文侧的下载量为零：页面上的汉字全部来自访客系统里已有的字体。要改字体只需改 `workspace_theme.py` 一处；换源顺序也是改 `src` 的两行；
- 回滚：`git revert c9df505eb7ffbd40148bd757c2fd085a7143081f` 后重新生成 archive 并发布（上一版为 `bc69ac1c847f99739e2b9db9c7c7c63cc9912d80`，本机源码备份 `/opt/trendradar-src-backup-20260912-221518`）；
- 未验证：访客侧的实际取字结果。本机与服务器的 curl 均 200，带 `Origin` 时主源回显 `access-control-allow-origin`、备源为 `*`，但 npmmirror 是 npm 注册表镜像、没有 SLA；要兜底就把这 7 个 woff2 放进自有对象存储再调整 `src` 顺序。

### 10.4 2026-09-12 第三次发布（首页信息架构整站上线）

- commit `f3865255`（代码；本节记录写在紧随其后的一个纯文档提交里），只改 `trendradar/report/` 三处与 `trendradar/digest/engine.py` 一处；
- 首页换成定稿原型的**工作台**信息架构：KPI 行 / 采集节律条 / 近 7 日入库量折线 / 本轮新增与更新动态 / 最新一期简报按板块分组的阅读流 / 简报后更新队列 / 全部新闻台账（搜索、板块与状态筛选、三种排序、每次 40 条、逐行已读、多源同题 `×N`、未来时间标 `?`）/ Markdown 导出，详见 §3.3；
- `trendradar/report/workspace_theme.py` 的六支令牌换成 tech-utility 方向的 oklch 原值（浅色与深色各一套，派生色一律 `oklch()`），仪表盘、简报存档、简报详情三处共用它，所以一次改动覆盖全部公开 HTML 页面；强调色只留在图表线与端点、主按钮；
- 简报节改为「板块分组 + 配额/入选」：配额随 section 从引擎下发（`engine.py::_public_digest` 的 `quota`），本轮零候选的板块在列表末尾用一行说明；
- **修掉一个线上错误**：首页载荷的 `_ci` 按「首次出现顺序」编号，而下发给浏览器的 `categories` 按「简报板块顺序」重排，两者错位，导致台账每一行的板块名指向别的板块（实测 NHK 政治条目显示为「游戏」）。现在重排后重新映射 `_ci`，并加了回归用例（`test_category_indices_survive_the_option_list_reorder`）。生产复核 917 条可核对条目、0 处错位；
- 控件边框对比度从 1.69:1 提到 3.11:1（`--line-strong`，两个主题各算一次）；简报存档的按下态筛选按钮此前是深色叠深色，一并修正；调色板审计脚本见设计工作区的 `check-contrast.py`（24 对逐项 PASS）；
- `workspace_template.py` 现在由设计工作区的 `build-production-ia.py` 从定稿原型生成，**不要手改**；
- 部署前：全量用例 **123** 通过（本地与生产 venv 各一次）、`py_compile` 通过、`precheck.sh` 输出 `PRECHECK: PASS`；archive 两端 sha256 一致（`1e0a903a438ef28df5c625ead989b20de889219aa9e91aa76f919be0429c988b`）；
- 部署后：23:30 那轮采集（`23:30:00 → 23:33:35`，`Result=success`，翻译 40/40、8.6s）重新生成了首页；线上 50 项检查全过 —— 18 个新 IA 区域、载荷四个新鲜度字段、917 条板块名与来源配置零错位、7 个拉丁字重且零 Inter、零 serif、私有路径四条 404、gzip 与 `text/html` 正常、简报存档与详情继承同一套令牌；
- 回滚：`git revert f3865255` 后等下一轮采集重新生成首页（上一版为 `8bfa70f8`，本机源码备份 `/opt/trendradar-src-backup-20260912-231953`）；
- 未验证：**手机断点只做了静态核对**（≤1080 / ≤980 / ≤720 三档规则逐条读过，未做窄视口渲染；渲染器视口固定 1080 CSS px，无法用它验窄屏）；深色主题同样只核对了令牌与对比度数值，未截图。若要真机确认，用手机打开站点即可。

### 10.5 2026-09-12 第四次发布（开屏改为简报优先）

- commit `ea11c7c013bb5dc397ab447caf937073a42d0817`（代码；本节记录写在紧随其后的一个纯文档提交里），只改 `trendradar/report/workspace_template.py` 与 `tests/test_homepage.py`；
- 起因：首页开屏是 KPI 行 + 采集节律条 + 入库量折线，打开站点先看到的是仪表盘而不是新闻。现在首屏是**最新一期简报**，仪表盘折进第七节之前的 `运行概览`（`<details id="overview">`，默认收起），新增区块顺序见 §3.3；
- 模板仍是生成物：设计工作区的 `build-production-ia.py` 里订单 MARKUP 的区块顺序 + 新增 `DASHBOARD` 常量（拼进 `__DASHBOARD__`），CSS 从原型 `index.html` 逐字节提取，**不要手改 `workspace_template.py`**；
- 顺手去掉重复标题：顶栏已经写明「新闻工作台」，页内那个 40px 的 `<h1 class="page-title">` 与其响应式覆盖一并删除，全页只有一个 `<h1>`（本期简报标题）；
- 新增回归用例 `test_the_page_opens_on_the_briefing_not_the_dashboard`：断言 meta → digest → queue → overview → ledger 的相对顺序、`<details>` 默认不展开、仪表盘的 kpis / cadence / sparkLine / feed / provenance / nextCrawlAt 全部在折叠内、全页无 `page-title` 且 `<h1>` 恰好一个；
- 部署前：全量用例 **124** 通过、`py_compile` 通过、`precheck.sh` 输出 `PRECHECK: PASS`；
- 部署后：等下一轮采集重新生成首页，线上逐项核对开屏顺序与折叠块（本轮检查脚本见设计工作区的 `verify-live-ia.py`）；
- 回滚：`git revert ea11c7c0` 后等下一轮采集重新生成首页（上一版为 `d996010b`）；
- 未验证：手机断点与深色主题仍只做静态核对（渲染器视口固定 1080 CSS px）；折叠块在窄屏的换行按静态规则核对。
### 10.6 2026-09-13 第五次发布（运行概览独立成页 + 表头吸顶修复）

- commit `6c63b574349f70bcca5b479187d314be5b599ee7`（代码；本节记录写在紧随其后的一个纯文档提交里）；
- 起因两条：① 首页开屏虽然已经是简报，但仪表盘仍折叠在首页里（用户要求「放进侧边栏新开一个页面」）；
  ② 台账表头显示错误 —— `.db-head` 的 sticky 不生效；
- 表头根因：`.db` 上的 `overflow: hidden`（本意裁圆角）让 `.db` 自己成了滚动容器，sticky 的参照物
  从页面变成 `.db`，表头被恒定下推一个 `--bar-h` 压在头两行上（线上截图里行文字被裁成半行）。
  改为 `overflow: clip`：圆角保留，且 clip 不创建滚动容器。详见 §3.3.1；
- 运行概览：删掉首页的 `<details id="overview">`，侧栏新增「运行概览」→ `/overview/`，页面体与
  运行时由生成器在**同一节切开**（`build-production-ia.py` 按运行时自带的 section banner 切分）：
  读数页拿到 KPI / 折线 / 动态 / 倒计时，首页拿到队列 / 台账 / 导出；`html.py` 用 `page="overview"`
  选文档，两页共用同一次载荷计算，所以 KPI 与台账小标题不可能对不上；
- 新增 `trendradar/report/overview_template.py`（生成物）；`generator.py` 多写
  `output/overview/index.html`，`publish_static.py` 把它复制到 `public/overview/`；
- 用例：全量 **128** 通过（原 124 + 读数页 3 条 + 发布 1 条新增/改写）；`py_compile` 通过；
  `git diff --check` 干净；服务器 `PRECHECK: PASS`，archive 两端 sha256 一致
  （`df4a549393215a0b74ed0128259db8793875ac4c1614925436a921f4bb222696`）；
- 部署前用设计工作区的检查脚本在**真实数据**上跑过两页：生产渲染器 + 线上 926 条快照 →
  `production-workbench-preview.html` / `production-overview-preview.html`，脚本（最小 DOM stub）
  实跑页面脚本：首页 40 行台账、读数页 KPI 926/101/13/114、折线 7 点、动态 8 行，均无异常；
- 部署后：01:00 那轮采集（01:00:01 → 01:03:35，`Result=success`，翻译 40/40）重新生成两页并发布，
  `public/overview/index.html` 330594 B、其 `.gz` 100303 B；线上逐项核对 **60/60 通过**
  （脚本见设计工作区的 `verify-live-readings.py`）：首页区块顺序 meta → 简报 → 队列 → 台账、
  无折叠块与读数元素、`.db` 规则为 `overflow: clip` 且 `.db-head` 仍 `position: sticky; top: var(--bar-h)`、
  `/overview/` 200 且含全部读数元素、不含台账/队列/导出元素、只有一个 `<h1>` 与一个实心按钮、
  侧栏在首页与 `/briefings/` 都能指到 `../overview/`、`/overview/` 把自己标为当前页、
  四个私有路径仍 404；
- 回滚：`git revert 6c63b574` 后等下一轮采集重新生成（上一版为 `ea11c7c0`，见 §10.5）；源码备份
  `/opt/trendradar-src-backup-20260913-003136`；
- 未验证：手机断点与深色主题仍只做静态核对；读数页的 sticky 顶栏在分段截图里会重复出现一次
  （渲染器把高页拼接时的产物，不是页面缺陷）。

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

### 采集每轮跑 10 分钟以上

1. 直接看 `[简报] 翻译回填: N/M 条入库, K 次调用, X.Xs` 这一行，它给出本轮实际调用次数与耗时
   （2026-09-11 之前没有这一行，那一步在日志里完全静默）；
2. 用 `systemctl show trendradar-collect.service -p ExecMainStartTimestamp` 与日志里的
   Starting/Deactivated 相减得到整轮真实耗时；
3. 若「次调用」明显大于 1：核对 `digest.translation` 与 `TRANSLATION_*` 是否被改大（详见 4.4）；
4. 看 `output/briefings/.translations.json` 的 `entries` 是否在增长：不增长说明请求都被拒了，
   再看 `refused` 里被拒条目的时间戳；
5. 不要在生产里加插桩再跑——在 `/tmp` 用 `/opt/trendradar/.venv/bin/python` 单独调用
   `AITranslator.translate_batch` 测批次耗时与成败（本机 `Documents\News\ops\probe_batch.py` 就是这个用途）。

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
8. 仅从已提交 commit 生成生产 archive，并用本机 `Documents\News\ops\` 的 `precheck.sh` / `deploy.sh` 完成预检与上线；
9. 部署后手动触发一次 service，并用 HTTPS 验证首页、归档和敏感路径；
10. 更新本文件中的验证事实和新限制。

接手时最重要的约束是：`output` 是私有持久状态，`public` 是可随时重建的公开白名单；任何部署方式都必须维持这条边界。
