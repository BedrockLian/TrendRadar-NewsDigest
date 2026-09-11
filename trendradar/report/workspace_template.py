# coding=utf-8
"""HTML shell for the public TrendRadar news workspace."""

DOCUMENT = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#071923">
  <title>热点新闻分析 · TrendRadar</title>
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource-variable/inter@5.2.8/index.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <script>
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
  </script>
  <style>
    :root {
      color-scheme: light;
      --app-bg: #eef3f6;
      --surface: #ffffff;
      --surface-raised: #f7fafb;
      --sidebar: #f8fafb;
      --sidebar-active: #dff4f6;
      --ink: #0c1c29;
      --ink-strong: #07131e;
      --muted: #64778a;
      --faint: #91a0ad;
      --rule: #d7e1e6;
      --rule-strong: #bdcbd2;
      --accent: #079aac;
      --accent-bright: #16c7d3;
      --accent-soft: #def5f6;
      --signal: #e74658;
      --signal-soft: #ffeaed;
      --focus: #13b9c8;
      --backdrop: rgba(4, 16, 24, .52);
      --font-ui: "Inter Variable", Inter, "HarmonyOS Sans SC", MiSans, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
      --font-mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --app-bg: #071923;
      --surface: #0a1d27;
      --surface-raised: #0d2430;
      --sidebar: #081821;
      --sidebar-active: #153746;
      --ink: #e9f0f3;
      --ink-strong: #ffffff;
      --muted: #9eb0be;
      --faint: #6f8492;
      --rule: #29414d;
      --rule-strong: #3b5866;
      --accent: #43d6df;
      --accent-bright: #5ce7ee;
      --accent-soft: #123b46;
      --signal: #ff5968;
      --signal-soft: #472530;
      --focus: #66e8ee;
      --backdrop: rgba(0, 0, 0, .7);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; scroll-padding-top: 84px; }
    body {
      margin: 0;
      background: var(--app-bg);
      color: var(--ink);
      font-family: var(--font-ui);
      font-size: 15px;
      line-height: 1.5;
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
    }
    button, input, select { font: inherit; }
    button, select { cursor: pointer; }
    a { color: inherit; }
    a:hover { color: var(--accent); }
    :focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
    [hidden] { display: none !important; }
    .sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
    }

    .app-frame {
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      min-height: 100vh;
      transition: grid-template-columns .22s ease;
    }
    .sidebar {
      position: sticky;
      top: 0;
      z-index: 50;
      display: flex;
      flex-direction: column;
      min-width: 0;
      height: 100vh;
      overflow: hidden auto;
      background: var(--sidebar);
      border-right: 1px solid var(--rule);
      transition: transform .22s ease, visibility .22s ease;
    }
    .sidebar-head {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 72px;
      padding: 14px 14px 14px 18px;
      border-bottom: 1px solid var(--rule);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      color: var(--ink-strong);
      font-size: 1.18rem;
      font-weight: 730;
      letter-spacing: -.02em;
      text-decoration: none;
    }
    .brand i { color: var(--accent); font-size: 1.35rem; }
    .sidebar-toggle, .top-icon-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      flex: 0 0 auto;
      border: 1px solid var(--rule);
      border-radius: 5px;
      background: transparent;
      color: var(--muted);
    }
    .sidebar-toggle { margin-left: auto; }
    .sidebar-toggle:hover, .top-icon-button:hover { color: var(--ink); background: var(--surface-raised); }

    .sidebar-nav { display: grid; gap: 4px; padding: 14px 10px; }
    .sidebar-nav a {
      display: grid;
      grid-template-columns: 22px minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px;
      min-height: 42px;
      padding: 0 12px;
      border-left: 3px solid transparent;
      border-radius: 5px;
      color: var(--muted);
      font-weight: 570;
      text-decoration: none;
    }
    .sidebar-nav a:hover { color: var(--ink); background: var(--surface-raised); }
    .sidebar-nav a[aria-current="page"] {
      color: var(--ink-strong);
      background: var(--sidebar-active);
      border-left-color: var(--accent);
    }
    .sidebar-nav i { font-size: 1rem; }
    .nav-count { color: var(--faint); font-size: .78rem; font-weight: 520; }

    .sidebar-section { padding: 16px 18px; border-top: 1px solid var(--rule); }
    .sidebar-section h2 {
      margin: 0 0 12px;
      color: var(--muted);
      font-size: .72rem;
      font-weight: 680;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .sidebar-date { margin: -5px 0 10px 28px; color: var(--faint); font-size: .76rem; }
    .sidebar-editions .edition-rail {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr;
      padding: 0;
    }
    .sidebar-editions .slot {
      min-height: 36px;
      padding: 7px 0 7px 28px;
      border-top: 0;
      border-left: 1px solid var(--rule-strong);
    }
    .sidebar-editions .slot::before { top: 14px; left: -4px; }
    .sidebar-editions .slot.next::after { display: none; }
    .sidebar-editions .slot time { min-width: 45px; }

    .sidebar-categories { display: grid; gap: 3px; }
    .sidebar-category {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      width: 100%;
      min-height: 36px;
      padding: 7px 10px;
      border: 0;
      border-left: 3px solid transparent;
      border-radius: 4px;
      background: transparent;
      color: var(--muted);
      text-align: left;
    }
    .sidebar-category:hover:not(:disabled) { color: var(--ink); background: var(--surface-raised); }
    .sidebar-category[aria-pressed="true"] {
      color: var(--ink-strong);
      background: var(--sidebar-active);
      border-left-color: var(--accent);
    }
    .sidebar-category strong { color: var(--faint); font-size: .76rem; font-weight: 550; }
    .sidebar-category:disabled { opacity: .42; cursor: default; }
    .sidebar-empty { color: var(--faint); font-size: .8rem; }
    .sidebar-footer { margin-top: auto; padding: 14px 18px; border-top: 1px solid var(--rule); }
    .sidebar-theme {
      display: flex;
      align-items: center;
      gap: 10px;
      width: 100%;
      padding: 9px 10px;
      border: 0;
      border-radius: 4px;
      background: transparent;
      color: var(--muted);
      text-align: left;
    }
    .sidebar-theme:hover { color: var(--ink); background: var(--surface-raised); }

    .app-page { min-width: 0; }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 40;
      display: flex;
      align-items: center;
      gap: 16px;
      min-height: 72px;
      padding: 12px 24px;
      background: var(--surface);
      border-bottom: 1px solid var(--rule);
    }
    .sidebar-expand { display: none; }
    .command-search {
      display: flex;
      align-items: center;
      gap: 10px;
      width: min(100%, 820px);
      min-width: 180px;
      height: 42px;
      padding: 0 12px;
      border: 1px solid var(--rule-strong);
      border-radius: 6px;
      background: var(--surface-raised);
      color: var(--muted);
    }
    .command-search:focus-within { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
    .command-search input {
      min-width: 0;
      flex: 1;
      border: 0;
      outline: 0;
      background: transparent;
      color: var(--ink);
    }
    .command-search input::placeholder { color: var(--faint); }
    .command-key {
      min-width: 24px;
      padding: 1px 6px;
      border: 1px solid var(--rule);
      border-radius: 4px;
      color: var(--faint);
      font: .72rem var(--font-mono);
      text-align: center;
    }
    .topbar-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-left: auto;
      color: var(--muted);
      font-size: .78rem;
      white-space: nowrap;
    }
    .top-theme-label { display: none; }

    .top-editions { display: none; background: var(--surface); border-bottom: 1px solid var(--rule); }
    .edition-rail {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      width: 100%;
      padding: 20px 28px 18px;
    }
    .slot {
      position: relative;
      display: flex;
      align-items: baseline;
      gap: 9px;
      padding-top: 9px;
      border-top: 1px solid var(--rule-strong);
      color: var(--muted);
    }
    .slot::before {
      content: "";
      position: absolute;
      top: -4px;
      left: 0;
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--rule-strong);
    }
    .slot:not(:last-child) { padding-right: 22px; }
    .slot.published, .slot.active { color: var(--ink); border-color: var(--accent); }
    .slot.published::before, .slot.active::before { background: var(--accent-bright); }
    .slot.next::after { content: "下一期"; margin-left: auto; color: var(--accent); font-size: .68rem; }
    .slot time { color: inherit; font: .79rem var(--font-mono); }
    .slot span { font-size: .78rem; }

    .alert-strip {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 9px 24px;
      background: var(--signal);
      color: #fff;
      font-size: .82rem;
    }
    .alert-label { font-weight: 760; letter-spacing: .08em; }
    .alert-items { display: flex; flex-wrap: wrap; gap: 10px; min-width: 0; }
    .alert-items a { text-decoration: none; }
    .alert-items a:hover { color: #fff; text-decoration: underline; }

    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) clamp(320px, 26vw, 380px);
      align-items: start;
      min-width: 0;
    }
    .workspace:has(> .updates-pane[hidden]) { grid-template-columns: minmax(0, 1fr); }
    .main-column { min-width: 0; background: var(--surface); }
    .main-column > section { padding: 32px 24px; }
    .main-column > section + section { border-top: 1px solid var(--rule); }
    .updates-pane {
      position: sticky;
      top: 72px;
      min-width: 0;
      max-height: calc(100vh - 72px);
      overflow: auto;
      padding: 32px 24px;
      background: var(--surface);
      border-left: 1px solid var(--rule);
    }
    .updates-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--rule);
    }
    .updates-head h2 { margin: 0; font-size: 1.35rem; line-height: 1.2; letter-spacing: -.02em; }
    .updates-head p { margin: 7px 0 0; color: var(--muted); font-size: .82rem; }
    .updates-all-link { color: var(--accent); font-size: .78rem; font-weight: 650; white-space: nowrap; }

    .edition-heading, .section-heading {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 22px;
    }
    .section-kicker {
      margin: 0 0 7px;
      color: var(--accent);
      font-size: .72rem;
      font-weight: 640;
      letter-spacing: .06em;
    }
    h1, .section-heading h2 {
      margin: 0;
      color: var(--ink-strong);
      font-family: var(--font-ui);
      font-weight: 740;
      letter-spacing: -.035em;
    }
    h1 { font-size: clamp(2rem, 3.25vw, 3.25rem); line-height: 1.08; }
    .section-heading h2 { font-size: 1.65rem; line-height: 1.15; }
    .edition-actions { display: grid; justify-items: end; gap: 10px; }
    .edition-ledger, .updates-intro, .all-news-ledger {
      margin: 0;
      color: var(--muted);
      font-size: .78rem;
    }
    .download-link {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 38px;
      padding: 7px 12px;
      border: 1px solid var(--accent);
      border-radius: 5px;
      color: var(--accent);
      font-size: .8rem;
      font-weight: 650;
      text-decoration: none;
    }
    .download-link:hover { color: var(--ink-strong); background: var(--accent-soft); }
    .download-link span { font-family: var(--font-mono); }

    .digest-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin: 0 0 20px;
    }
    .digest-filter:not(.sidebar-category) {
      flex: 0 0 auto;
      min-height: 34px;
      padding: 6px 10px;
      border: 1px solid var(--rule-strong);
      border-radius: 5px;
      background: transparent;
      color: var(--muted);
      font-size: .76rem;
      white-space: nowrap;
    }
    .digest-filter:not(.sidebar-category):hover:not(:disabled) { color: var(--ink); border-color: var(--accent); }
    .digest-filter:not(.sidebar-category)[aria-pressed="true"] {
      color: #04171d;
      background: var(--accent-bright);
      border-color: var(--accent-bright);
      font-weight: 670;
    }
    .digest-filter span { margin-left: 3px; font-family: var(--font-mono); }
    .digest-filter:disabled { opacity: .42; cursor: default; }
    .digest-table-head, .digest-row {
      display: grid;
      grid-template-columns: 36px 58px minmax(260px, 1fr) 104px 86px minmax(104px, 132px);
      gap: 12px;
      align-items: start;
    }
    .digest-table-head {
      padding: 0 0 10px;
      color: var(--faint);
      font-size: .68rem;
      font-weight: 640;
    }
    .digest-row { padding: 18px 0; border-top: 1px solid var(--rule); }
    .digest-meta { display: contents; }
    .article-number { padding-top: 2px; color: var(--signal); font: 650 .76rem var(--font-mono); }
    .digest-state { min-height: 24px; }
    .status-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 38px;
      min-height: 24px;
      padding: 2px 7px;
      border-radius: 4px;
      color: var(--signal);
      background: var(--signal-soft);
      font-size: .68rem;
      font-weight: 680;
      white-space: nowrap;
    }
    .status-突发, .status-breaking { color: #fff; background: var(--signal); }
    .article-copy { min-width: 0; }
    .article-heading { display: flex; align-items: flex-start; gap: 8px; }
    .article-heading h2, .news-row h3 {
      min-width: 0;
      margin: 0;
      color: var(--ink-strong);
      font-family: var(--font-ui);
      font-size: 1rem;
      font-weight: 650;
      line-height: 1.34;
      letter-spacing: -.012em;
      overflow-wrap: anywhere;
    }
    .article-heading a, .news-row h3 a { text-decoration: none; }
    .article-heading a:hover, .news-row h3 a:hover { text-decoration: underline; text-decoration-color: var(--accent); }
    .article-summary {
      display: -webkit-box;
      max-width: 760px;
      margin: 6px 0 0;
      overflow: hidden;
      color: var(--muted);
      font-size: .82rem;
      line-height: 1.42;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    }
    .article-meta { display: flex; flex-wrap: wrap; gap: 7px; margin: 8px 0 0; color: var(--muted); font-size: .72rem; }
    .digest-source, .digest-time { padding-top: 2px; color: var(--muted); font-size: .72rem; overflow-wrap: anywhere; }
    .digest-time { font-family: var(--font-mono); white-space: nowrap; }
    .digest-category, .news-category-label {
      justify-self: start;
      padding: 4px 7px;
      border-radius: 4px;
      color: var(--accent);
      background: var(--accent-soft);
      font-size: .68rem;
      font-weight: 620;
      line-height: 1.35;
    }
    .empty-state {
      min-height: 240px;
      display: grid;
      place-content: center;
      justify-items: center;
      gap: 8px;
      border-top: 1px solid var(--rule);
      color: var(--muted);
      text-align: center;
    }
    .empty-state strong { color: var(--ink-strong); font-size: 1.1rem; }

    .analysis-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 32px; border-top: 1px solid var(--rule); }
    .analysis-grid article { padding: 20px 0; border-bottom: 1px solid var(--rule); }
    .analysis-grid h3 { margin: 0 0 7px; color: var(--accent); font-size: .78rem; }
    .analysis-grid p { margin: 0; white-space: pre-line; font-size: .86rem; }

    .updates-list, .all-news-list { border-bottom: 1px solid var(--rule); }
    .news-row {
      display: grid;
      grid-template-columns: 38px minmax(0, 1fr) 150px;
      gap: 12px;
      padding: 18px 0;
      border-top: 1px solid var(--rule);
    }
    .news-row-side { padding-top: 2px; color: var(--muted); font-size: .69rem; text-align: right; }
    .news-row-side span, .news-row-side time { display: block; }
    .news-row-side .news-category-label { display: inline-block; margin-top: 5px; }
    .update-row { grid-template-columns: 56px minmax(0, 1fr); padding: 18px 0; }
    .update-row .article-number { color: var(--muted); font-size: .7rem; }
    .update-row .article-heading { display: grid; grid-template-columns: auto minmax(0, 1fr); }
    .update-row .article-heading h3 { grid-column: 2; font-size: .92rem; }
    .update-row .article-heading .status-badge { grid-column: 1; grid-row: 1; }
    .update-row .article-summary { display: none; }
    .update-row .news-row-side {
      grid-column: 2;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 7px;
      padding: 7px 0 0 46px;
      text-align: left;
    }
    .update-row .news-row-side span, .update-row .news-row-side time { display: inline-block; }
    .update-row .news-row-side time { display: none; }
    .update-row .news-row-side .news-category-label { margin-top: 0; }

    .news-controls {
      display: grid;
      grid-template-columns: minmax(220px, 2fr) repeat(3, minmax(130px, 1fr));
      gap: 10px;
      margin: 22px 0 14px;
    }
    .control { display: grid; gap: 5px; }
    .control span { color: var(--muted); font-size: .68rem; }
    .control input, .control select {
      width: 100%;
      min-width: 0;
      min-height: 40px;
      padding: 8px 10px;
      border: 1px solid var(--rule-strong);
      border-radius: 5px;
      background: var(--surface-raised);
      color: var(--ink);
      font-size: .82rem;
    }
    .results-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 12px 0; }
    #results-count { margin: 0; color: var(--muted); font-size: .76rem; }
    .reset-button, .load-more {
      min-height: 36px;
      padding: 7px 12px;
      border: 1px solid var(--rule-strong);
      border-radius: 5px;
      background: transparent;
      color: var(--ink);
      font-size: .76rem;
    }
    .reset-button:hover, .load-more:hover { color: var(--accent); border-color: var(--accent); }
    .load-more { display: block; min-width: 140px; margin: 24px auto 0; }
    .filter-empty { padding: 30px 0 12px; color: var(--muted); text-align: center; }
    .site-footer {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 20px 24px 28px;
      border-top: 1px solid var(--rule);
      color: var(--faint);
      font-size: .7rem;
    }

    html[data-sidebar="collapsed"] .app-frame { grid-template-columns: 0 minmax(0, 1fr); }
    html[data-sidebar="collapsed"] .sidebar { transform: translateX(-100%); visibility: hidden; }
    html[data-sidebar="collapsed"] .sidebar-expand { display: inline-flex; }
    html[data-sidebar="collapsed"] .top-editions { display: block; }

    .sidebar-scrim {
      position: fixed;
      inset: 0;
      z-index: 45;
      display: none;
      border: 0;
      background: var(--backdrop);
    }

    @media (max-width: 1180px) {
      .app-frame { grid-template-columns: 220px minmax(0, 1fr); }
      .workspace { grid-template-columns: minmax(0, 1fr) 320px; }
      .digest-table-head, .digest-row { grid-template-columns: 32px 52px minmax(220px, 1fr) 90px 82px; }
      .digest-table-head > :last-child, .digest-category { display: none; }
      .news-controls { grid-template-columns: minmax(200px, 2fr) repeat(3, minmax(110px, 1fr)); }
    }
    @media (max-width: 960px) {
      html { scroll-padding-top: 76px; }
      .app-frame, html[data-sidebar="collapsed"] .app-frame { grid-template-columns: minmax(0, 1fr); }
      .sidebar, html[data-sidebar="collapsed"] .sidebar {
        position: fixed;
        left: 0;
        top: 0;
        width: min(300px, calc(100vw - 56px));
        transform: translateX(-102%);
        visibility: hidden;
        box-shadow: 18px 0 60px rgba(0, 0, 0, .22);
      }
      html[data-drawer="open"] .sidebar { transform: translateX(0); visibility: visible; }
      html[data-drawer="open"] .sidebar-scrim { display: block; }
      .sidebar-expand, html[data-sidebar="collapsed"] .sidebar-expand { display: inline-flex; }
      .top-editions, html[data-sidebar="expanded"] .top-editions { display: block; }
      .topbar { min-height: 64px; padding: 10px 16px; }
      .topbar-meta time { display: none; }
      .workspace { grid-template-columns: minmax(0, 1fr); }
      .updates-pane {
        position: static;
        max-height: none;
        border-top: 1px solid var(--rule);
        border-left: 0;
      }
      .main-column > section, .updates-pane { padding: 28px 20px; }
      .news-controls { grid-template-columns: 1fr 1fr; }
      .control-search { grid-column: 1 / -1; }
    }
    @media (max-width: 720px) {
      .topbar { gap: 10px; }
      .top-icon-button { width: 38px; height: 38px; }
      .topbar-meta { gap: 4px; }
      .command-key { display: none; }
      .edition-rail { padding: 18px 16px 16px; }
      .slot { display: grid; gap: 2px; }
      .slot.next::after { display: none; }
      .main-column > section, .updates-pane { padding: 24px 16px; }
      .edition-heading, .section-heading { align-items: flex-start; flex-direction: column; gap: 12px; }
      .edition-actions { justify-items: start; }
      h1 { font-size: clamp(1.85rem, 10vw, 2.55rem); }
      .digest-filters { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 5px; scrollbar-width: thin; }
      .digest-table-head { display: none; }
      .digest-row {
        grid-template-columns: 30px minmax(0, 1fr);
        gap: 8px 10px;
        padding: 18px 0;
      }
      .article-number { grid-column: 1; grid-row: 1 / span 3; }
      .digest-state { grid-column: 2; min-height: 20px; }
      .digest-row .article-copy { grid-column: 2; }
      .digest-meta {
        grid-column: 2;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 7px;
      }
      .digest-source, .digest-time { padding-top: 0; }
      .digest-category { display: inline-block; }
      .article-heading h2, .news-row h3 { font-size: .98rem; }
      .article-summary { font-size: .8rem; }
      .news-row { grid-template-columns: 30px minmax(0, 1fr); gap: 10px; }
      .news-row-side { grid-column: 2; display: flex; flex-wrap: wrap; gap: 7px; padding: 0; text-align: left; }
      .news-row-side span, .news-row-side time { display: inline-block; }
      .news-row-side .news-category-label { margin-top: 0; }
      .update-row { grid-template-columns: 52px minmax(0, 1fr); }
      .update-row .article-number { grid-row: auto; }
      .analysis-grid { grid-template-columns: 1fr; }
      .news-controls { grid-template-columns: 1fr; }
      .control-search { grid-column: auto; }
      .site-footer { display: grid; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
    @media print {
      .sidebar, .topbar, .top-editions, .alert-strip, .updates-pane, #all-news, .site-footer, .digest-filters { display: none !important; }
      .app-frame { display: block; }
      body, .main-column { background: #fff; color: #000; }
      .digest-row { break-inside: avoid; }
    }
  </style>
</head>
<body>
  <button class="sidebar-scrim" id="sidebar-scrim" type="button" aria-label="关闭导航"></button>
  <div class="app-frame">
    <aside class="sidebar" id="app-sidebar" aria-label="主导航">
      <div class="sidebar-head">
        <a class="brand" href="#digest"><i class="bi bi-bullseye" aria-hidden="true"></i><span>TrendRadar</span></a>
        <button class="sidebar-toggle" type="button" data-sidebar-toggle aria-controls="app-sidebar" aria-expanded="true" aria-label="收起导航" title="收起导航">
          <i class="bi bi-layout-sidebar-inset" aria-hidden="true"></i>
        </button>
      </div>
      <nav class="sidebar-nav">
        <a href="#digest" aria-current="page"><i class="bi bi-layout-text-window" aria-hidden="true"></i><span>最新一期</span></a>
        <a id="updates-nav" href="#updates"__UPDATES_HIDDEN__><i class="bi bi-bell" aria-hidden="true"></i><span>简报后更新</span><strong class="nav-count">__UPDATE_COUNT__</strong></a>
        <a href="#all-news"><i class="bi bi-list-task" aria-hidden="true"></i><span>全部新闻</span><strong class="nav-count">__TOTAL_COUNT__</strong></a>
        <a href="briefings/"><i class="bi bi-archive" aria-hidden="true"></i><span>简报存档</span></a>
      </nav>
      <section class="sidebar-section">
        <h2>今日简报</h2>
        <p class="sidebar-date">__GENERATED_DATE__</p>
        <div class="sidebar-editions">__SLOTS__</div>
      </section>
      <section class="sidebar-section">
        <h2>新闻分类</h2>
        <div class="sidebar-categories">__SIDEBAR_CATEGORIES__</div>
      </section>
      <div class="sidebar-footer">
        <button class="sidebar-theme" type="button" data-theme-toggle><i class="bi bi-moon" aria-hidden="true"></i><span>深色模式</span></button>
      </div>
    </aside>

    <div class="app-page">
      <header class="topbar">
        <button class="top-icon-button sidebar-expand" type="button" data-sidebar-toggle aria-controls="app-sidebar" aria-expanded="false" aria-label="展开导航" title="展开导航">
          <i class="bi bi-list" aria-hidden="true"></i>
        </button>
        <label class="command-search" for="header-search">
          <i class="bi bi-search" aria-hidden="true"></i>
          <input id="header-search" type="search" autocomplete="off" placeholder="搜索新闻、来源或关键词…">
          <span class="command-key" aria-hidden="true">/</span>
        </label>
        <div class="topbar-meta">
          <time>__GENERATED_DATE__</time>
          <button class="top-icon-button" type="button" data-theme-toggle aria-label="切换深浅色模式" title="切换深浅色模式"><i class="bi bi-moon" aria-hidden="true"></i><span class="top-theme-label">深色</span></button>
        </div>
      </header>
      <div class="top-editions">__SLOTS__</div>
      __ALERTS__

      <div class="workspace">
        <main class="main-column">
          __DIGEST__
          __AI_ANALYSIS__
          <section class="all-news-section" id="all-news" aria-labelledby="all-news-title">
            <div class="section-heading">
              <div><p class="section-kicker">本轮抓取</p><h2 id="all-news-title">全部新闻</h2></div>
              <p class="all-news-ledger">__TOTAL_COUNT__ 篇 · __SOURCE_COUNT__ 个来源</p>
            </div>
            <div class="news-controls">
              <label class="control control-search"><span>搜索</span><input id="news-search" type="search" autocomplete="off" placeholder="标题、摘要或来源"></label>
              <label class="control"><span>分类</span><select id="news-category"><option value="all">全部分类</option>__CATEGORY_OPTIONS__</select></label>
              <label class="control"><span>来源</span><select id="news-source"><option value="all">全部来源</option></select></label>
              <label class="control"><span>排序</span><select id="news-sort"><option value="newest">最新优先</option><option value="oldest">最早优先</option></select></label>
            </div>
            <div class="results-toolbar">
              <p id="results-count" aria-live="polite"></p>
              <button class="reset-button" id="reset-filters" type="button">重置筛选</button>
            </div>
            <div class="all-news-list" id="all-news-list"></div>
            <p class="filter-empty" id="all-news-empty" hidden>没有符合当前筛选条件的新闻。</p>
            <button class="load-more" id="load-more" type="button">加载更多</button>
          </section>
        </main>

        <aside class="updates-pane" id="updates" aria-labelledby="updates-title"__UPDATES_HIDDEN__>
          <div class="updates-head">
            <div><h2 id="updates-title">简报后更新</h2><p>本期发布后 · __UPDATE_COUNT__ 条更新</p></div>
            <a class="updates-all-link" href="#all-news">查看全部 <i class="bi bi-arrow-right" aria-hidden="true"></i></a>
          </div>
          <div class="updates-list" id="updates-list"></div>
        </aside>
      </div>
      <footer class="site-footer"><span>热点新闻分析 · 个人工作台</span><span>更新于 __GENERATED_AT__ · 北京时间</span></footer>
    </div>
  </div>

  <script id="homepage-data" type="application/json">__HOMEPAGE_DATA__</script>
  <script id="summaries-data" type="application/json">__SUMMARIES_DATA__</script>
  <script>
    (function () {
      'use strict';
      var root = document.documentElement;
      var dataNode = document.getElementById('homepage-data');
      var data = { updates: [], allNews: [], categories: [], sources: [] };
      try { data = JSON.parse(dataNode.textContent || '{}'); } catch (_) {}

      // "updates since the briefing" ships as positions into allNews rather
      // than a duplicated copy of every article object.
      data.updates = (data.updates || []).map(function (index) {
        return typeof index === 'number' ? data.allNews[index] : index;
      }).filter(Boolean);
      // source_name / category_name ship as lookup indices to keep the payload
      // small; resolve them back to display strings once, here.
      (data.allNews || []).forEach(function (item) {
        if (typeof item._si === 'number') item.source_name = (data.sources || [])[item._si] || item.source_name;
        if (typeof item._ci === 'number') item.category_name = (data.categories || [])[item._ci] || item.category_name;
      });

      // Summaries ship inline as a dense, positional array so the payload and
      // this array cannot drift, then an identical sidecar is fetched right
      // after first paint.  The fetch keeps the summary *array* cacheable on
      // its own and lets the page render long before it lands.
      var summariesNode = document.getElementById('summaries-data');
      var SUMMARIES_URL = '__SUMMARIES_FILENAME__';
      var summaries = [];
      try { summaries = JSON.parse(summariesNode.textContent || '[]') || []; } catch (_) { summaries = []; }
      // Position in the original payload array, so the positional summary
      // array stays correct after the "newest/oldest" sort reorders the list.
      (data.allNews || []).forEach(function (item, index) { item._oi = index; });
      data.updates.forEach(function (item, index) { item._oi = -1 - index; });
      function summaryOf(item, index) {
        if (!item) return '';
        var at = typeof item._oi === 'number' ? item._oi : index;
        var value = summaries[at];
        return typeof value === 'string' ? value : '';
      }
      function loadSummaries() {
        if (typeof fetch !== 'function' || location.protocol === 'file:') return;
        fetch(SUMMARIES_URL, { credentials: 'same-origin' })
          .then(function (response) { return response.ok ? response.json() : null; })
          .then(function (payload) {
            if (!Array.isArray(payload)) return;
            summaries = payload;
            renderUpdates();
            renderAll();
          })
          .catch(function () { /* inline copy stays authoritative */ });
      }

      var PAGE_SIZE = 40;
      var FILTER_KEY = 'trendradar-filters-v1';
      var SIDEBAR_KEY = 'trendradar-sidebar-collapsed';
      var shown = PAGE_SIZE;
      var search = document.getElementById('news-search');
      var headerSearch = document.getElementById('header-search');
      var category = document.getElementById('news-category');
      var source = document.getElementById('news-source');
      var sort = document.getElementById('news-sort');
      var list = document.getElementById('all-news-list');
      var count = document.getElementById('results-count');
      var loadMore = document.getElementById('load-more');
      var empty = document.getElementById('all-news-empty');
      var mobileSidebar = matchMedia('(max-width: 960px)');

      function safeUrl(value) {
        try {
          var parsed = new URL(value, location.href);
          return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : '';
        } catch (_) { return ''; }
      }
      function statusLabel(value) {
        if (value === 'breaking' || value === '突发') return '突发';
        if (value === 'updated' || value === '更新') return '更新';
        if (value === 'new') return '新';
        return '';
      }
      function displayTime(value) {
        if (!value) return '';
        var parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return value;
        return new Intl.DateTimeFormat('zh-CN', {
          month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
        }).format(parsed).replace('/', '-');
      }
      function articleRow(item, index, compact) {
        var article = document.createElement('article');
        article.className = compact ? 'news-row update-row' : 'news-row';

        var number = document.createElement('span');
        number.className = 'article-number';
        number.setAttribute('aria-hidden', 'true');
        number.textContent = compact ? displayTime(item.published_at || '').slice(-5) : String(index + 1).padStart(2, '0');
        article.appendChild(number);

        var copy = document.createElement('div');
        copy.className = 'article-copy';
        var headingWrap = document.createElement('div');
        headingWrap.className = 'article-heading';
        var heading = document.createElement('h3');
        var href = safeUrl(item.url || '');
        if (href) {
          var link = document.createElement('a');
          link.href = href;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = item.title || '';
          heading.appendChild(link);
        } else {
          heading.textContent = item.title || '';
        }
        var label = statusLabel(item.status || '');
        if (label) {
          var badge = document.createElement('span');
          badge.className = 'status-badge status-' + (label === '突发' ? 'breaking' : 'updated');
          badge.textContent = label;
          headingWrap.appendChild(badge);
        }
        headingWrap.appendChild(heading);
        copy.appendChild(headingWrap);
        if (!compact) {
          var summaryText = summaryOf(item, index);
          if (summaryText) {
            var summary = document.createElement('p');
            summary.className = 'article-summary';
            summary.textContent = summaryText;
            copy.appendChild(summary);
          }
        }
        article.appendChild(copy);

        var side = document.createElement('div');
        side.className = 'news-row-side';
        var sourceText = document.createElement('span');
        sourceText.textContent = item.source_name || 'RSS';
        side.appendChild(sourceText);
        if (item.published_at) {
          var time = document.createElement('time');
          time.dateTime = item.published_at;
          time.textContent = displayTime(item.published_at);
          side.appendChild(time);
        }
        var categoryText = document.createElement('span');
        categoryText.className = 'news-category-label';
        categoryText.textContent = item.category_name || '其他重要新闻';
        side.appendChild(categoryText);
        article.appendChild(side);
        return article;
      }
      function renderUpdates() {
        var target = document.getElementById('updates-list');
        if (!target) return;
        var fragment = document.createDocumentFragment();
        data.updates.slice(0, 10).forEach(function (item, index) { fragment.appendChild(articleRow(item, index, true)); });
        target.replaceChildren(fragment);
      }
      function filteredNews() {
        var query = search.value.trim().toLocaleLowerCase('zh-CN');
        var selectedCategory = category.value;
        var selectedSource = source.value;
        var items = data.allNews.filter(function (item) {
          var haystack = [item.title, summaryOf(item, item._oi), item.source_name].join(' ').toLocaleLowerCase('zh-CN');
          return (!query || haystack.indexOf(query) !== -1) &&
            (selectedCategory === 'all' || item.category_name === selectedCategory) &&
            (selectedSource === 'all' || item.source_name === selectedSource);
        });
        items.sort(function (left, right) {
          var a = Date.parse(left.published_at || '') || 0;
          var b = Date.parse(right.published_at || '') || 0;
          return sort.value === 'oldest' ? a - b : b - a;
        });
        return items;
      }
      function saveFilters() {
        try {
          localStorage.setItem(FILTER_KEY, JSON.stringify({
            search: search.value, category: category.value, source: source.value, sort: sort.value
          }));
        } catch (_) {}
      }
      function renderAll() {
        var items = filteredNews();
        var visible = items.slice(0, shown);
        var fragment = document.createDocumentFragment();
        visible.forEach(function (item, index) { fragment.appendChild(articleRow(item, index, false)); });
        list.replaceChildren(fragment);
        count.textContent = '显示 ' + visible.length + ' / ' + items.length + ' 篇';
        empty.hidden = items.length !== 0;
        loadMore.hidden = visible.length >= items.length;
        headerSearch.value = search.value;
        saveFilters();
      }

      Array.from(new Set(data.allNews.map(function (item) { return item.source_name; }).filter(Boolean)))
        .sort(function (a, b) { return a.localeCompare(b, 'zh-CN'); })
        .forEach(function (name) {
          var option = document.createElement('option');
          option.value = name;
          option.textContent = name;
          source.appendChild(option);
        });
      try {
        var saved = JSON.parse(localStorage.getItem(FILTER_KEY) || '{}');
        if (typeof saved.search === 'string') search.value = saved.search;
        if (Array.from(category.options).some(function (option) { return option.value === saved.category; })) category.value = saved.category;
        if (Array.from(source.options).some(function (option) { return option.value === saved.source; })) source.value = saved.source;
        if (saved.sort === 'newest' || saved.sort === 'oldest') sort.value = saved.sort;
      } catch (_) {}
      [search, category, source, sort].forEach(function (control) {
        control.addEventListener('input', function () { shown = PAGE_SIZE; renderAll(); });
        control.addEventListener('change', function () { shown = PAGE_SIZE; renderAll(); });
      });
      headerSearch.addEventListener('input', function () {
        search.value = headerSearch.value;
        shown = PAGE_SIZE;
        renderAll();
      });
      headerSearch.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        document.getElementById('all-news').scrollIntoView();
        search.focus();
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === '/' && !/input|select|textarea/i.test(document.activeElement.tagName)) {
          event.preventDefault();
          headerSearch.focus();
        }
      });
      loadMore.addEventListener('click', function () { shown += PAGE_SIZE; renderAll(); });
      document.getElementById('reset-filters').addEventListener('click', function () {
        search.value = '';
        headerSearch.value = '';
        category.value = 'all';
        source.value = 'all';
        sort.value = 'newest';
        shown = PAGE_SIZE;
        renderAll();
      });

      document.querySelectorAll('.digest-filter').forEach(function (button) {
        button.addEventListener('click', function () {
          var selected = button.dataset.category;
          var visible = 0;
          document.querySelectorAll('.digest-filter').forEach(function (item) {
            item.setAttribute('aria-pressed', String(item.dataset.category === selected));
          });
          document.querySelectorAll('.digest-row').forEach(function (row) {
            row.hidden = selected !== 'all' && row.dataset.category !== selected;
            if (!row.hidden) visible += 1;
          });
          var digestEmpty = document.getElementById('digest-filter-empty');
          if (digestEmpty) digestEmpty.hidden = visible !== 0;
          document.getElementById('digest').scrollIntoView();
          if (mobileSidebar.matches) closeDrawer();
        });
      });

      function syncTheme() {
        var dark = root.dataset.theme === 'dark';
        document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
          button.setAttribute('aria-label', dark ? '切换到浅色模式' : '切换到深色模式');
          button.setAttribute('title', dark ? '切换到浅色模式' : '切换到深色模式');
          var icon = button.querySelector('i');
          if (icon) icon.className = dark ? 'bi bi-sun' : 'bi bi-moon';
          var label = button.querySelector('span');
          if (label) label.textContent = dark ? '浅色模式' : '深色模式';
          var shortLabel = button.querySelector('.top-theme-label');
          if (shortLabel) shortLabel.textContent = dark ? '浅色' : '深色';
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

      function closeDrawer() {
        root.dataset.drawer = 'closed';
        syncSidebarButtons();
      }
      function syncSidebarButtons() {
        var open = mobileSidebar.matches ? root.dataset.drawer === 'open' : root.dataset.sidebar !== 'collapsed';
        document.querySelectorAll('[data-sidebar-toggle]').forEach(function (button) {
          button.setAttribute('aria-expanded', String(open));
          button.setAttribute('aria-label', open ? '收起导航' : '展开导航');
          button.setAttribute('title', open ? '收起导航' : '展开导航');
        });
      }
      function toggleSidebar() {
        if (mobileSidebar.matches) {
          root.dataset.drawer = root.dataset.drawer === 'open' ? 'closed' : 'open';
        } else {
          var collapsed = root.dataset.sidebar !== 'collapsed';
          root.dataset.sidebar = collapsed ? 'collapsed' : 'expanded';
          try { localStorage.setItem(SIDEBAR_KEY, String(collapsed)); } catch (_) {}
        }
        syncSidebarButtons();
      }
      document.querySelectorAll('[data-sidebar-toggle]').forEach(function (button) { button.addEventListener('click', toggleSidebar); });
      document.getElementById('sidebar-scrim').addEventListener('click', closeDrawer);
      document.addEventListener('keydown', function (event) { if (event.key === 'Escape') closeDrawer(); });
      document.querySelectorAll('.sidebar-nav a').forEach(function (link) {
        link.addEventListener('click', function () { if (mobileSidebar.matches) closeDrawer(); });
      });
      function syncNav() {
        var hash = location.hash || '#digest';
        document.querySelectorAll('.sidebar-nav a[href^="#"]').forEach(function (link) {
          if (link.getAttribute('href') === hash) link.setAttribute('aria-current', 'page');
          else link.removeAttribute('aria-current');
        });
      }
      window.addEventListener('hashchange', syncNav);
      if (mobileSidebar.addEventListener) mobileSidebar.addEventListener('change', function () { closeDrawer(); });

      root.dataset.drawer = 'closed';
      renderUpdates();
      renderAll();
      syncTheme();
      syncSidebarButtons();
      syncNav();

      // First paint is already done. Pull the authoritative summary array and
      // re-render once it lands; until then the inline copy above is in use.
      if (document.readyState === 'complete') loadSummaries();
      else window.addEventListener('load', loadSummaries);
    })();
  </script>
</body>
</html>
'''
