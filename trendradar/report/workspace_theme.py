"""Shared visual shell for the public TrendRadar workspace pages.

Font delivery rule — one webfont for Latin and digits, nothing for Chinese:

* Latin and digits use Fontsource IBM Plex (``IBM Plex Sans`` / ``IBM Plex Mono``),
  declared below with a Latin-only ``unicode-range`` so a Chinese character never
  triggers a font request.  7 files / 135.8 KB total.
* Chinese always resolves through the system stack (PingFang / Microsoft YaHei /
  Noto Sans SC / ...).  A CJK webfont would cost one to three orders of magnitude
  more per weight (self-hosted subset 266 KB, whole package 1.09 MB, Google's
  sharded ``css2`` 1.91 MB for this site's real character set) for no gain.
* The monospace stack must end in a CJK sans fallback, never in generic
  ``monospace``: on a Chinese Windows box Chrome maps generic ``monospace`` to
  Songti, so digits rendered from that stack come out as serif glyphs.
"""

from __future__ import annotations

import html
from typing import Optional


HEAD_ASSETS = """  <link rel="preconnect" href="https://registry.npmmirror.com" crossorigin>
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">"""


THEME_BOOTSTRAP_SCRIPT = r"""  <script>
    try {
      var storedTheme = localStorage.getItem('trendradar-theme');
      if (storedTheme === 'dark' || (!storedTheme && matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.dataset.theme = 'dark';
      }
      var storedSidebar = localStorage.getItem('trendradar-sidebar-collapsed');
      document.documentElement.dataset.sidebar = storedSidebar === 'true' ? 'collapsed' : 'expanded';
    } catch (_) {
      document.documentElement.dataset.sidebar = 'expanded';
    }
  </script>"""


THEME_CSS = r"""
    /* ---- 拉丁与数字：Fontsource IBM Plex（仅拉丁子集，版本锁 5.3.0） --------------
       中文一律走系统栈，所以这些声明的 unicode-range 只覆盖拉丁区段，中文永远
       不会触发字体请求。每个字重两个源同序降级：主源 registry.npmmirror.com、
       备源 cdn.jsdelivr.net（同文件字节数逐字重比对过，sha256 一致）。7 个文件
       合计约 136 KB。这里不再引入 Inter Variable —— 整包第三方 CSS 正是我们要
       去掉的那类依赖，也是中文页面里最容易被当成默认脸的那种字形。 */
    @font-face { font-family:'IBM Plex Sans'; font-style:normal; font-weight:400; font-display:swap;
        src:url('https://registry.npmmirror.com/@fontsource/ibm-plex-sans/5.3.0/files/files/ibm-plex-sans-latin-400-normal.woff2') format('woff2'),
            url('https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-sans@5.3.0/files/ibm-plex-sans-latin-400-normal.woff2') format('woff2');
        unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family:'IBM Plex Sans'; font-style:normal; font-weight:500; font-display:swap;
        src:url('https://registry.npmmirror.com/@fontsource/ibm-plex-sans/5.3.0/files/files/ibm-plex-sans-latin-500-normal.woff2') format('woff2'),
            url('https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-sans@5.3.0/files/ibm-plex-sans-latin-500-normal.woff2') format('woff2');
        unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family:'IBM Plex Sans'; font-style:normal; font-weight:600; font-display:swap;
        src:url('https://registry.npmmirror.com/@fontsource/ibm-plex-sans/5.3.0/files/files/ibm-plex-sans-latin-600-normal.woff2') format('woff2'),
            url('https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-sans@5.3.0/files/ibm-plex-sans-latin-600-normal.woff2') format('woff2');
        unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family:'IBM Plex Sans'; font-style:normal; font-weight:700; font-display:swap;
        src:url('https://registry.npmmirror.com/@fontsource/ibm-plex-sans/5.3.0/files/files/ibm-plex-sans-latin-700-normal.woff2') format('woff2'),
            url('https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-sans@5.3.0/files/ibm-plex-sans-latin-700-normal.woff2') format('woff2');
        unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family:'IBM Plex Mono'; font-style:normal; font-weight:400; font-display:swap;
        src:url('https://registry.npmmirror.com/@fontsource/ibm-plex-mono/5.3.0/files/files/ibm-plex-mono-latin-400-normal.woff2') format('woff2'),
            url('https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-400-normal.woff2') format('woff2');
        unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family:'IBM Plex Mono'; font-style:normal; font-weight:600; font-display:swap;
        src:url('https://registry.npmmirror.com/@fontsource/ibm-plex-mono/5.3.0/files/files/ibm-plex-mono-latin-600-normal.woff2') format('woff2'),
            url('https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-600-normal.woff2') format('woff2');
        unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    @font-face { font-family:'IBM Plex Mono'; font-style:normal; font-weight:700; font-display:swap;
        src:url('https://registry.npmmirror.com/@fontsource/ibm-plex-mono/5.3.0/files/files/ibm-plex-mono-latin-700-normal.woff2') format('woff2'),
            url('https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-700-normal.woff2') format('woff2');
        unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
    :root {
      color-scheme: light;
      /* tech-utility（Datadog / GitHub 一脉）方向库原值。派生色一律用 oklch()
         或 color-mix 生成，不引入自造 hex —— 页面里所有灰阶都是这六支的亲属，
         换方向只需换这一处。 */
      --bg:          oklch(98% 0.005 250);
      --surface:     oklch(100% 0 0);
      --ink:         oklch(22% 0.02 240);
      --muted:       oklch(50% 0.018 240);
      --rule:        oklch(90% 0.008 240);
      --accent:      oklch(58% 0.16 145);
      --bg-soft:     oklch(96% 0.006 250);
      --bg-hover:    oklch(93.5% 0.009 250);
      --ink-2:       var(--muted);
      --ink-3:       oklch(52% 0.016 240);
      --line:        var(--rule);
      --line-strong: oklch(66% 0.012 240);
      --accent-ink:  oklch(44% 0.13 145);
      --accent-deep: oklch(37% 0.11 145);
      --accent-soft: oklch(95% 0.025 145);
      --warn:        oklch(62% 0.14 75);
      --signal:      oklch(48% 0.16 27);
      --signal-soft: oklch(95% 0.028 27);
      --focus:       oklch(50% 0.14 250);
      --backdrop:    oklch(22% 0.02 240 / .45);
      /* 别名层：简报存档与详情页沿用旧变量名，值全部指向上面的六支，
         这样两个页面不必改一行也能跟着换色，且不留第二套色。 */
      --app-bg: var(--bg);
      --surface-raised: var(--bg-soft);
      --sidebar: var(--bg-soft);
      --sidebar-active: var(--bg-hover);
      --ink-strong: var(--ink);
      --faint: var(--ink-3);
      --rule-strong: var(--line-strong);
      --accent-bright: var(--accent-ink);
      --radius-sm: 3px;
      --radius-md: 5px;
      --radius-lg: 8px;
      --bar-h: 48px;
      --font-ui: "IBM Plex Sans", "Segoe UI", "Segoe UI Variable Text", system-ui, -apple-system, "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
      --font-mono: "IBM Plex Mono", "Cascadia Mono", "SFMono-Regular", Consolas, "DejaVu Sans Mono", "Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", ui-monospace, sans-serif;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      /* 同一套令牌的深色档：对比度逐对按 oklch 的 L* 算过，
         正文 12.9:1、次要文字 5.5:1、主按钮 7.0:1。 */
      --bg:          oklch(19% 0.014 250);
      --surface:     oklch(22.5% 0.016 250);
      --ink:         oklch(93% 0.008 250);
      --muted:       oklch(71% 0.016 250);
      --rule:        oklch(31% 0.015 250);
      --accent:      oklch(72% 0.15 145);
      --bg-soft:     oklch(24.5% 0.016 250);
      --bg-hover:    oklch(29% 0.02 250);
      --ink-3:       oklch(64% 0.015 250);
      --line-strong: oklch(52% 0.015 250);
      --accent-ink:  oklch(80% 0.14 145);
      --accent-deep: oklch(87% 0.12 145);
      --accent-soft: oklch(31% 0.05 145);
      --warn:        oklch(78% 0.13 75);
      --signal:      oklch(72% 0.15 27);
      --signal-soft: oklch(31% 0.06 27);
      --focus:       oklch(75% 0.13 250);
      --backdrop:    oklch(0% 0 0 / .68);
    }
"""


SHELL_CSS = r"""
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; scroll-padding-top: calc(var(--bar-h) + 12px); }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: var(--font-ui);
      font-size: 14px;
      line-height: 1.5;
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
    }
    button, input, select { font: inherit; }
    button, select { cursor: pointer; }
    a { color: inherit; }
    a:hover { color: var(--accent-ink); }
    :focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
    [hidden] { display: none !important; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

    .app-frame { display: grid; grid-template-columns: 240px minmax(0, 1fr); min-height: 100vh; transition: grid-template-columns .22s ease; }
    .sidebar { position: sticky; top: 0; z-index: 50; display: flex; flex-direction: column; min-width: 0; height: 100vh; overflow: hidden auto; background: var(--bg-soft); border-right: 1px solid var(--line); transition: transform .22s ease, visibility .22s ease; }
    .sidebar-head { display: flex; align-items: center; gap: 8px; min-height: 56px; padding: 10px 10px 10px 16px; border-bottom: 1px solid var(--line); }
    .brand { display: flex; align-items: center; gap: 9px; min-width: 0; color: var(--ink); font-size: 1.02rem; font-weight: 600; letter-spacing: -.01em; text-decoration: none; }
    .brand i { color: var(--ink-3); font-size: 1.15rem; }
    .sidebar-toggle, .top-icon-button { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; flex: 0 0 auto; border: 1px solid var(--line-strong); border-radius: var(--radius-sm); background: transparent; color: var(--muted); }
    .sidebar-toggle { margin-left: auto; }
    .sidebar-toggle:hover, .top-icon-button:hover { color: var(--ink); background: var(--bg-hover); }
    .sidebar-nav { display: grid; gap: 2px; padding: 12px 8px; }
    .sidebar-nav a { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 9px; min-height: 34px; padding: 0 10px; border-left: 2px solid transparent; border-radius: var(--radius-sm); color: var(--muted); font-size: .87rem; font-weight: 500; text-decoration: none; }
    .sidebar-nav a:hover { color: var(--ink); background: var(--bg-hover); }
    .sidebar-nav a[aria-current="page"] { color: var(--ink); background: var(--bg-hover); border-left-color: var(--line-strong); font-weight: 600; }
    .sidebar-nav i { font-size: .95rem; }
    .nav-count { color: var(--ink-3); font-size: .76rem; font-weight: 500; font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
    .sidebar-section { padding: 12px 14px; border-top: 1px solid var(--line); }
    .sidebar-section h2 { margin: 0 0 10px; color: var(--ink-3); font-size: .68rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; font-family: var(--font-mono); }
    .sidebar-footer { margin-top: auto; padding: 12px 14px; border-top: 1px solid var(--line); }
    .sidebar-theme { display: flex; align-items: center; gap: 9px; width: 100%; padding: 7px 9px; border: 0; border-radius: var(--radius-sm); background: transparent; color: var(--muted); font-size: .87rem; text-align: left; }
    .sidebar-theme:hover { color: var(--ink); background: var(--bg-hover); }
    .app-page { min-width: 0; }
    .topbar { position: sticky; top: 0; z-index: 40; display: flex; align-items: center; gap: 14px; min-height: var(--bar-h); padding: 7px 18px; background: var(--surface); border-bottom: 1px solid var(--line); }
    .sidebar-expand { display: none; }
    .topbar-title { min-width: 0; display: flex; align-items: center; gap: 9px; color: var(--ink); font-weight: 600; font-size: .95rem; }
    .topbar-title i { color: var(--ink-3); }
    .topbar-meta { display: flex; align-items: center; gap: 10px; margin-left: auto; color: var(--muted); font-size: .78rem; white-space: nowrap; font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
    .top-theme-label { display: none; }
    .sidebar-scrim { position: fixed; inset: 0; z-index: 45; display: none; border: 0; background: var(--backdrop); }
    html[data-sidebar="collapsed"] .app-frame { grid-template-columns: 0 minmax(0, 1fr); }
    html[data-sidebar="collapsed"] .sidebar { transform: translateX(-100%); visibility: hidden; }
    html[data-sidebar="collapsed"] .sidebar-expand { display: inline-flex; }

    @media (max-width: 1180px) { .app-frame { grid-template-columns: 220px minmax(0, 1fr); } }
    @media (max-width: 960px) {
      html { scroll-padding-top: calc(var(--bar-h) + 8px); }
      .app-frame, html[data-sidebar="collapsed"] .app-frame { grid-template-columns: minmax(0, 1fr); }
      .sidebar, html[data-sidebar="collapsed"] .sidebar { position: fixed; left: 0; top: 0; width: min(300px, calc(100vw - 56px)); transform: translateX(-102%); visibility: hidden; box-shadow: 18px 0 60px rgba(0, 0, 0, .22); }
      html[data-drawer="open"] .sidebar { transform: translateX(0); visibility: visible; }
      html[data-drawer="open"] .sidebar-scrim { display: block; }
      .sidebar-expand, html[data-sidebar="collapsed"] .sidebar-expand { display: inline-flex; }
      .topbar { padding: 7px 14px; }
      .topbar-meta time { display: none; }
    }
    @media (max-width: 720px) { .topbar { gap: 10px; } .topbar-meta { gap: 4px; } }
    @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; } }
"""


SHELL_BEHAVIOR_SCRIPT = r"""  <script>
    (function () {
      var root = document.documentElement;
      var mobileSidebar = matchMedia('(max-width: 960px)');
      function closeDrawer() { root.dataset.drawer = 'closed'; syncSidebarButtons(); }
      function syncSidebarButtons() {
        var open = mobileSidebar.matches ? root.dataset.drawer === 'open' : root.dataset.sidebar !== 'collapsed';
        document.querySelectorAll('[data-sidebar-toggle]').forEach(function (button) {
          button.setAttribute('aria-expanded', String(open));
          button.setAttribute('aria-label', open ? '收起导航' : '展开导航');
          button.setAttribute('title', open ? '收起导航' : '展开导航');
        });
      }
      function toggleSidebar() {
        if (mobileSidebar.matches) root.dataset.drawer = root.dataset.drawer === 'open' ? 'closed' : 'open';
        else {
          var collapsed = root.dataset.sidebar !== 'collapsed';
          root.dataset.sidebar = collapsed ? 'collapsed' : 'expanded';
          try { localStorage.setItem('trendradar-sidebar-collapsed', String(collapsed)); } catch (_) {}
        }
        syncSidebarButtons();
      }
      function syncTheme() {
        var dark = root.dataset.theme === 'dark';
        document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
          button.setAttribute('aria-label', dark ? '切换到浅色模式' : '切换到深色模式');
          button.setAttribute('title', dark ? '切换到浅色模式' : '切换到深色模式');
          var icon = button.querySelector('i');
          if (icon) icon.className = dark ? 'bi bi-sun' : 'bi bi-moon';
          var label = button.querySelector('span');
          if (label) label.textContent = label.classList.contains('top-theme-label') ? (dark ? '浅色' : '深色') : (dark ? '浅色模式' : '深色模式');
        });
      }
      document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
        button.addEventListener('click', function () {
          var dark = root.dataset.theme === 'dark';
          root.dataset.theme = dark ? 'light' : 'dark';
          try { localStorage.setItem('trendradar-theme', dark ? 'light' : 'dark'); } catch (_) {}
          syncTheme();
        });
      });
      document.querySelectorAll('[data-sidebar-toggle]').forEach(function (button) { button.addEventListener('click', toggleSidebar); });
      var scrim = document.getElementById('sidebar-scrim');
      if (scrim) scrim.addEventListener('click', closeDrawer);
      document.addEventListener('keydown', function (event) { if (event.key === 'Escape') closeDrawer(); });
      document.querySelectorAll('.sidebar-nav a').forEach(function (link) { link.addEventListener('click', function () { if (mobileSidebar.matches) closeDrawer(); }); });
      if (mobileSidebar.addEventListener) mobileSidebar.addEventListener('change', closeDrawer);
      root.dataset.drawer = 'closed';
      syncTheme();
      syncSidebarButtons();
    })();
  </script>"""


def _nav_link(
    href: str,
    icon: str,
    label: str,
    *,
    active: bool = False,
    count: Optional[int] = None,
    hidden: bool = False,
    element_id: str = "",
) -> str:
    current = ' aria-current="page"' if active else ""
    hidden_attr = " hidden" if hidden else ""
    count_html = f'<strong class="nav-count">{count}</strong>' if count is not None else ""
    id_attr = f' id="{html.escape(element_id, quote=True)}"' if element_id else ""
    return (
        f'<a{id_attr} href="{html.escape(href, quote=True)}"{current}{hidden_attr}>'
        f'<i class="bi bi-{icon}" aria-hidden="true"></i><span>{html.escape(label)}</span>{count_html}</a>'
    )


def render_sidebar(
    *,
    root_href: str,
    active: str,
    update_count: Optional[int] = None,
    total_count: Optional[int] = None,
    extra_html: str = "",
    hide_empty_updates: bool = False,
) -> str:
    """Render the shared navigation sidebar using trusted, server-built extras."""

    root = root_href
    brand_href = f"{root}#digest" if root else "#digest"
    nav = "".join(
        [
            _nav_link(f"{root}#digest" if root else "#digest", "layout-text-window", "最新一期", active=active == "digest"),
            _nav_link(
                f"{root}#updates" if root else "#updates",
                "bell",
                "简报后更新",
                active=active == "updates",
                count=update_count,
                hidden=hide_empty_updates and update_count == 0,
                element_id="updates-nav",
            ),
            _nav_link(f"{root}#all-news" if root else "#all-news", "list-task", "全部新闻", active=active == "all-news", count=total_count),
            _nav_link(f"{root}briefings/" if root else "briefings/", "archive", "简报存档", active=active == "archive"),
        ]
    )
    return f"""    <aside class="sidebar" id="app-sidebar" aria-label="主导航">
      <div class="sidebar-head">
        <a class="brand" href="{html.escape(brand_href, quote=True)}"><i class="bi bi-bullseye" aria-hidden="true"></i><span>TrendRadar</span></a>
        <button class="sidebar-toggle" type="button" data-sidebar-toggle aria-controls="app-sidebar" aria-expanded="true" aria-label="收起导航" title="收起导航"><i class="bi bi-layout-sidebar-inset" aria-hidden="true"></i></button>
      </div>
      <nav class="sidebar-nav">{nav}</nav>
{extra_html}
      <div class="sidebar-footer"><button class="sidebar-theme" type="button" data-theme-toggle><i class="bi bi-moon" aria-hidden="true"></i><span>深色模式</span></button></div>
    </aside>"""


def render_topbar(title: str, icon: str, meta: str = "", meta_html: str = "") -> str:
    """Render the shared top bar.

    ``meta`` is plain text and gets escaped; ``meta_html`` is a trusted,
    server-built block (clocks, status pills) inserted before the theme toggle.
    """

    meta_block = f"<time>{html.escape(meta)}</time>" if meta else ""
    meta_block += meta_html
    return f"""      <header class="topbar">
        <button class="top-icon-button sidebar-expand" type="button" data-sidebar-toggle aria-controls="app-sidebar" aria-expanded="false" aria-label="展开导航" title="展开导航"><i class="bi bi-list" aria-hidden="true"></i></button>
        <div class="topbar-title"><i class="bi bi-{html.escape(icon, quote=True)}" aria-hidden="true"></i><span>{html.escape(title)}</span></div>
        <div class="topbar-meta">{meta_block}<button class="top-icon-button" type="button" data-theme-toggle aria-label="切换深浅色模式" title="切换深浅色模式"><i class="bi bi-moon" aria-hidden="true"></i></button></div>
      </header>"""
