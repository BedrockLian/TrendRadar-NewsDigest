# coding=utf-8
"""The 运行概览 readings page: KPI row, cadence strip, ingest chart, round feed.

Generated from the approved prototype (``build-production-ia.py``); edit that
script and re-run it rather than hand-editing the markup below.  It shares the
theme, the page CSS and the data-independent half of the runtime with
:mod:`trendradar.report.workspace_template`, so the two pages cannot disagree
about a number: the KPI row, the 7-day window and the cadence copy all come from
the same payload through the same code.

What this file owns: the page body (data provenance, KPI row, cadence strip,
7-day ingest chart, this round's new-and-updated feed) and the bootstrap that
renders those blocks only — no ledger, no queue, no export.
"""
DOCUMENT = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#fbfcfd" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#15181c" media="(prefers-color-scheme: dark)">
  <title>新闻工作台 · TrendRadar</title>
__WORKSPACE_HEAD__
  <style>
__WORKSPACE_THEME_CSS__
__WORKSPACE_SHELL_CSS__
  /* 页面级记号：状态色与三处淡色底。深色档在同名令牌上重算，
     所以页面里不再出现任何与主题无关的字面色。 */
  :root {
    --row-h: 36px;
    --tint-accent-fill: oklch(58% 0.16 145 / .10);
    --tint-accent-weak: oklch(58% 0.16 145 / .06);
    --tint-accent-strong: oklch(58% 0.16 145 / .18);
    --tint-accent-pulse: oklch(58% 0.16 145 / .5);
    --pill-new-bg: oklch(93% 0.035 245);  --pill-new-ink: oklch(40% 0.09 245);
    --pill-upd-bg: oklch(94% 0.05 75);    --pill-upd-ink: oklch(40% 0.08 60);
    --pill-old-bg: oklch(94% 0.006 250);  --pill-old-ink: oklch(44% 0.016 240);
  }
  :root[data-theme="dark"] {
    --row-h: 46px;
    --tint-accent-fill: oklch(72% 0.15 145 / .16);
    --tint-accent-weak: oklch(72% 0.15 145 / .10);
    --tint-accent-strong: oklch(72% 0.15 145 / .22);
    --tint-accent-pulse: oklch(72% 0.15 145 / .5);
    --pill-new-bg: oklch(31% 0.05 245);  --pill-new-ink: oklch(86% 0.06 245);
    --pill-upd-bg: oklch(32% 0.06 75);   --pill-upd-ink: oklch(88% 0.07 75);
    --pill-old-bg: oklch(27% 0.01 250);  --pill-old-ink: oklch(80% 0.012 250);
  }

  .chip-clock { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-2);
                font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 12px;
                border: 1px solid var(--line); border-radius: var(--radius-sm);
                padding: 2px 8px; background: var(--bg-soft); }
  .chip-clock b { color: var(--ink); font-weight: 600; }

  .pill-live { display: inline-flex; align-items: center; gap: 6px;
               padding: 2px 8px 2px 6px; background: var(--surface);
               border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
               font-size: 12px; color: var(--ink-2); }
  .pill-live .dot { width: 7px; height: 7px; border-radius: 50%;
                    background: var(--accent); box-shadow: 0 0 0 0 var(--tint-accent-pulse);
                    animation: pulse 1.8s infinite; }
  .pill-live.syncing .dot { background: var(--ink-3); animation: none; }
  .pill-live.stale   .dot { background: var(--warn); animation: none; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 var(--tint-accent-pulse); }
    70% { box-shadow: 0 0 0 6px oklch(58% 0.16 145 / 0); }
    100% { box-shadow: 0 0 0 0 oklch(58% 0.16 145 / 0); }
  }

  .page { padding: 40px max(32px, 5vw) 72px; max-width: 1160px; width: 100%; align-self: center; }

  .page-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
               color: var(--ink-2); font-size: 13px; margin-bottom: 24px; }
  .page-meta .sep { color: var(--ink-3); }
  .page-meta .who { width: 18px; height: 18px; border-radius: 50%; flex: 0 0 18px;
                    background: var(--ink); color: var(--surface);
                    display: inline-grid; place-items: center;
                    font-size: 10px; font-weight: 700; font-family: var(--mono); }

  .btn { display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px;
         font-size: 13px; color: var(--ink); background: var(--surface);
         border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
         cursor: pointer; transition: background .15s ease; font-family: inherit; }
  .btn:hover { background: var(--bg-hover); }
  .btn:focus-visible { outline: 2px solid var(--accent-ink); outline-offset: 1px; }
  .btn .ico { width: 14px; height: 14px; display: inline-block; }
  .btn .ico.spin { animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .btn.primary { background: var(--accent-ink); color: var(--surface); border-color: transparent; }
  .btn.primary:hover { background: var(--accent-deep); }
  .btn.ghost { border-color: transparent; color: var(--ink-2); }
  .btn.ghost:hover { background: var(--bg-hover); color: var(--ink); }
  .btn.sm { padding: 3px 8px; font-size: 12px; }

  .callout { background: var(--bg-soft); border: 1px solid var(--line);
             border-radius: var(--radius-md); padding: 12px 14px;
             display: flex; gap: 10px; align-items: flex-start;
             margin: 0 0 24px; color: var(--ink); font-size: 13px; }
  .callout .tag { font-family: var(--mono); font-size: 11px; color: var(--ink-2);
                  border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
                  padding: 1px 6px; flex: 0 0 auto; margin-top: 2px; letter-spacing: .04em; }
  .callout p { margin: 0; }
  .callout small { color: var(--ink-2); display: block; margin-top: 3px; }

  .kpis { display: grid; grid-template-columns: repeat(4, 1fr);
          gap: 1px; background: var(--line); border: 1px solid var(--line);
          border-radius: var(--radius-md); overflow: hidden; margin: 0 0 12px; }
  .kpi { background: var(--surface); padding: 16px 18px;
         display: flex; flex-direction: column; gap: 3px; }
  .kpi .label { color: var(--ink-2); font-size: 11.5px; letter-spacing: .04em;
                font-weight: 500; }
  .kpi .value { font-size: 32px; font-weight: 600; letter-spacing: -0.01em;
                color: var(--ink); font-variant-numeric: tabular-nums;
                font-family: var(--mono); transition: color .25s ease; }
  .kpi .value.flash { color: var(--accent-ink); }
  .kpi .delta { font-size: 12px; color: var(--ink-2); }
  .kpi .delta.up   { color: oklch(42% 0.11 150); }
  .kpi .delta.down { color: oklch(45% 0.13 27); }

  /* 采集节律条：发丝线四格，与 KPI 网格同族 */
  .strip { display: grid; grid-template-columns: repeat(4, 1fr);
           gap: 1px; background: var(--line); border: 1px solid var(--line);
           border-radius: var(--radius-md); overflow: hidden; margin: 0 0 28px; }
  .strip > div { background: var(--surface); padding: 10px 14px; min-width: 0; }
  .strip .k { color: var(--ink-3); font-size: 11px; letter-spacing: .04em; }
  .strip .v { font-family: var(--mono); font-variant-numeric: tabular-nums;
              font-size: 13px; color: var(--ink); margin-top: 2px; line-height: 1.5;
              overflow-wrap: anywhere; }
  .strip .v .sub { display: block; color: var(--ink-2); }

  h2.h { font-size: 17px; font-weight: 600; margin: 30px 0 4px; letter-spacing: -0.005em; }
  .h-sub { color: var(--ink-2); font-size: 12.5px; margin-bottom: 12px; }

  /* align-items: start —— 否则折线卡被右侧更长的动态列表拉高，
     卡片底部留出大片死白 */
  .two-col { display: grid; grid-template-columns: 1.05fr 1fr; gap: 20px;
             align-items: start; }
  .card { background: var(--surface); border: 1px solid var(--line);
          border-radius: var(--radius-md); padding: 14px 16px; min-width: 0; }
  .card-title { display: flex; align-items: baseline; justify-content: space-between;
                gap: 10px; font-size: 12.5px; color: var(--ink-2); margin-bottom: 8px; }
  .card-title strong { color: var(--ink); font-weight: 600; font-size: 13px; }
  .card-note { color: var(--ink-3); font-size: 11.5px; margin-top: 6px; line-height: 1.45; }
  .spark { width: 100%; height: 132px; display: block; }
  .spark-axis { fill: var(--ink-3); font-size: 10px; font-family: var(--mono); }
  .spark-fill { fill: var(--tint-accent-fill); }
  .spark-line { fill: none; stroke: var(--accent); stroke-width: 2; }
  .spark-dot  { fill: var(--accent); }
  .spark-grid line { stroke: var(--line); stroke-dasharray: 2 3; }
  .spark-val { fill: var(--ink-2); font-size: 10px; font-family: var(--mono); }

  .feed { display: flex; flex-direction: column; }
  .feed-row { display: flex; gap: 10px; padding: 8px 2px; border-bottom: 1px solid var(--line);
              align-items: flex-start; }
  .feed-row:last-child { border-bottom: none; }
  .feed-row .av { flex: 0 0 24px; width: 24px; height: 24px; border-radius: var(--radius-sm);
                  display: grid; place-items: center; color: oklch(100% 0 0); font-size: 10px;
                  font-weight: 700; letter-spacing: -0.02em; }
  .feed-row .body { flex: 1; min-width: 0; font-size: 12.5px; color: var(--ink); }
  .feed-row .body .who { font-weight: 600; }
  .feed-row .body .t { display: block; overflow: hidden; text-overflow: ellipsis;
                       white-space: nowrap; color: var(--ink-2); margin-top: 1px; }
  .feed-row .body .t:hover { color: var(--ink); text-decoration: underline; }
  .feed-row .time { color: var(--ink-3); font-size: 11px; flex: 0 0 auto;
                    font-family: var(--mono); font-variant-numeric: tabular-nums; }
  .feed-row.new { background: var(--tint-accent-weak); }
  .feed-row.new .body .who::before { content: "•"; color: var(--accent-ink); margin-right: 5px; }
  .empty { color: var(--ink-2); font-size: 12.5px; padding: 14px 2px; }

  /* ---------- toolbar ---------- */
  .tools { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
           padding: 10px 0; border-top: 1px solid var(--line); margin-top: 2px; }
  .tools .field { display: inline-flex; align-items: center; gap: 6px;
                  border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
                  background: var(--surface); padding: 3px 8px; }
  .tools label { color: var(--ink-3); font-size: 11px; letter-spacing: .04em; }
  .tools input[type="search"], .tools select {
    border: 0; background: transparent; color: var(--ink); font: inherit; font-size: 13px;
    padding: 2px 0; outline: none; min-width: 60px; }
  .tools input[type="search"] { width: 190px; }
  .tools .field:focus-within { border-color: var(--accent-ink); }
  .tools .spacer { flex: 1; }
  .tools .result { color: var(--ink-2); font-size: 12px; font-family: var(--mono);
                   font-variant-numeric: tabular-nums; }

  /* ---------- linked database ---------- */
  /* overflow: clip — not hidden.  `hidden` turns .db into a scroll container, and a
     sticky child then measures its offset against .db rather than the page: the header
     sat a full --bar-h below the container's top edge at every scroll position and
     covered the first two rows.  `clip` rounds the corners without creating a
     scrollport, so the header pins under the top bar the way it looks like it does. */
  .db { border: 1px solid var(--line); border-radius: var(--radius-md);
        overflow: clip; background: var(--surface); }
  .db-head, .db-row {
    display: grid; grid-template-columns: 34px minmax(0, 2.6fr) 1.05fr 1fr 0.95fr 0.85fr;
    align-items: center; padding: 0 12px; border-bottom: 1px solid var(--line);
    font-size: 13px; min-height: var(--row-h);
  }
  .db-head { background: var(--bg-soft); color: var(--ink-2); min-height: 32px;
             font-size: 11px; letter-spacing: .04em;
             font-weight: 500; position: sticky; top: var(--bar-h); z-index: 10; }
  .db-row:last-child { border-bottom: none; }
  .db-head { border-radius: var(--radius-md) var(--radius-md) 0 0; }
  .db-row:last-child { border-radius: 0 0 var(--radius-md) var(--radius-md); }
  .db-row:hover { background: var(--bg-soft); }
  .db-row.changed { animation: rowflash 1.4s ease; }
  @keyframes rowflash {
    0% { background: var(--tint-accent-strong); }
    100% { background: transparent; }
  }
  .db-cell { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .db-cell.title { display: flex; align-items: center; gap: 6px; }
  .db-cell.title a { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .db-cell.title a:hover { text-decoration: underline; }
  .db-cell.src { color: var(--ink-2); font-size: 12.5px; }
  .db-cell.when { font-family: var(--mono); font-variant-numeric: tabular-nums;
                  font-size: 12px; color: var(--ink-2); }
  .db-cell.when .future { color: var(--warn); }
  .db-cell .pill { display: inline-flex; align-items: center; gap: 4px;
                   padding: 1px 7px; border-radius: var(--radius-sm); font-size: 11.5px;
                   font-weight: 500; }
  .pill.new { background: var(--pill-new-bg); color: var(--pill-new-ink); }
  .pill.upd { background: var(--pill-upd-bg); color: var(--pill-upd-ink); }
  .pill.old { background: var(--pill-old-bg); color: var(--pill-old-ink); }
  .dup { font-family: var(--mono); font-size: 11px; color: var(--ink-3);
         border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 0 4px;
         flex: 0 0 auto; }
  .rd { width: 15px; height: 15px; accent-color: var(--accent-ink); margin: 0;
        cursor: pointer; display: block; }
  .rd:focus-visible { outline: 2px solid var(--accent-ink); outline-offset: 2px; }
  .db-more { display: flex; justify-content: center; padding: 10px; border-top: 1px solid var(--line);
             background: var(--surface); }
  .db-empty { padding: 22px 14px; color: var(--ink-2); font-size: 13px; text-align: center; }

  .footer { margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--line);
            color: var(--ink-3); font-size: 12px; display: flex; align-items: center;
            gap: 8px; flex-wrap: wrap; }
  .footer .key { font-family: var(--mono); background: var(--bg-soft); padding: 1px 5px;
                 border-radius: var(--radius-sm); color: var(--ink-2); }
  .footer a.key:hover { color: var(--ink); }

  .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%) translateY(6px);
           background: var(--ink); color: var(--bg); padding: 8px 14px;
           border-radius: var(--radius-md); font-size: 12.5px;
           opacity: 0; pointer-events: none; z-index: 60;
           transition: opacity .2s ease, transform .2s ease; }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

  /* 导出面板 */
  .sheet { position: fixed; inset: 0; background: var(--backdrop);
           display: none; z-index: 70; }
  .sheet.open { display: block; }
  .sheet-panel { position: fixed; left: 50%; bottom: 0; transform: translateX(-50%);
                 width: min(900px, calc(100% - 32px)); max-height: 72vh;
                 background: var(--surface); border: 1px solid var(--line-strong);
                 border-radius: var(--radius-lg) var(--radius-lg) 0 0;
                 display: flex; flex-direction: column; z-index: 71; }
  .sheet-head { display: flex; align-items: center; gap: 10px; padding: 12px 16px;
                border-bottom: 1px solid var(--line); }
  .sheet-head strong { font-size: 14px; }
  .sheet-head .count { color: var(--ink-2); font-size: 12px; font-family: var(--mono); }
  .sheet-body { overflow: auto; padding: 0; }
  .sheet-body pre { margin: 0; padding: 14px 16px; font-family: var(--mono);
                    font-size: 12px; line-height: 1.6; color: var(--ink);
                    white-space: pre-wrap; word-break: break-word; }
  .sheet-foot { display: flex; align-items: center; gap: 8px; padding: 10px 16px;
                border-top: 1px solid var(--line); }
  .sheet-foot .hint { color: var(--ink-3); font-size: 11.5px; }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
  @media (max-width: 1080px) {
    .two-col { grid-template-columns: 1fr; }
    .db-head, .db-row { grid-template-columns: 34px minmax(0, 2.4fr) 1fr 0.95fr 0.9fr; }
    .db-cell.src { display: none; }
  }
  @media (max-width: 980px) {
    .page { padding: 28px 18px 64px; }
    .kpis { grid-template-columns: repeat(2, 1fr); }
    .strip { grid-template-columns: repeat(2, 1fr); }
    .db-head { position: static; }
    :root { --row-h: 46px; }
    .db-head, .db-row { grid-template-columns: 40px minmax(0, 1fr) 0.85fr; }
    .db-cell.src, .db-cell.when { display: none; }
    .tools input[type="search"] { width: 100%; }
    .tools .field { flex: 1 1 140px; }
  }
  .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .section-kicker { margin: 0 0 5px; color: var(--ink-3); font-size: 11px;
                    letter-spacing: .06em; font-family: var(--mono); }

  /* ---------- 突发条：用状态色，不占强调色预算 ---------- */
  .alert-strip { display: flex; align-items: flex-start; gap: 10px; margin: 0 0 24px;
                 padding: 9px 12px; background: var(--signal-soft);
                 border: 1px solid var(--signal-soft); border-radius: var(--radius-sm);
                 font-size: 12.5px; }
  .alert-strip .alert-label { flex: 0 0 auto; color: var(--signal); font-weight: 600;
                 font-size: 11.5px; letter-spacing: .04em; padding-top: 1px; }
  .alert-strip .alert-items { min-width: 0; display: flex; flex-wrap: wrap;
                 align-items: baseline; gap: 3px 8px; color: var(--ink); }
  .alert-strip .alert-items > span { color: var(--ink-3); }
  .alert-strip .alert-items a:hover { text-decoration: underline; }

  /* ---------- 侧栏：今日简报 / 新闻分类（与简报存档共用同一套外观） ---------- */
  .sidebar-date { margin: 0 0 8px; color: var(--ink-3); font-size: .78rem;
                  font-family: var(--font-mono); }
  .sidebar-editions { display: grid; gap: 2px; }
  .edition-rail { display: grid; gap: 2px; }
  .slot { display: flex; align-items: center; gap: 8px; padding: 3px 7px;
          border-radius: var(--radius-sm); color: var(--muted); font-size: .8rem; }
  .slot time { color: var(--ink-3); font-family: var(--font-mono); font-size: .78rem;
               font-variant-numeric: tabular-nums; }
  .slot.published { color: var(--ink); background: var(--bg-hover); }
  .slot.published time { color: var(--ink); }
  .slot.next { color: var(--ink); font-weight: 600; }
  .slot.active { color: var(--ink); }
  .sidebar-categories { display: grid; gap: 2px; }
  .sidebar-category { display: flex; align-items: center; justify-content: space-between;
                      gap: 8px; width: 100%; min-height: 30px; padding: 5px 9px; border: 0;
                      border-left: 2px solid transparent; border-radius: var(--radius-sm);
                      background: transparent; color: var(--muted); font-size: .82rem; text-align: left; }
  .sidebar-category:hover { color: var(--ink); background: var(--bg-hover); }
  .sidebar-category[aria-pressed="true"] { color: var(--ink); background: var(--bg-hover);
                      border-left-color: var(--line-strong); font-weight: 600; }
  .sidebar-category strong { color: var(--ink-3); font-size: .76rem; font-weight: 500;
                      font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .sidebar-empty { color: var(--ink-3); font-size: .8rem; }
  /* ---------- 简报（读）：按板块分组，配额写在组头上 ---------- */
  .digest-section { margin-top: 34px; }
  .edition-heading { display: flex; flex-wrap: wrap; align-items: flex-end;
                     justify-content: space-between; gap: 10px 20px;
                     padding-bottom: 12px; border-bottom: 1px solid var(--line-strong); }
  .edition-heading .section-kicker { margin: 0 0 5px; color: var(--ink-3);
                     font-size: 11px; letter-spacing: .06em; font-family: var(--mono); }
  .edition-heading h1 { margin: 0; font-size: 26px; font-weight: 700;
                        letter-spacing: -0.01em; line-height: 1.2; }
  .edition-heading h1 a:hover { text-decoration: underline; }
  .edition-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
  .edition-ledger { margin: 0; color: var(--ink-2); font-size: 12.5px;
                    font-family: var(--mono); font-variant-numeric: tabular-nums; }
  .download-link { color: var(--accent-ink); font-size: 12.5px; }
  .download-link:hover { text-decoration: underline; }
  .empty-heading { border-bottom-color: var(--line); }
  .empty-state { display: grid; gap: 4px; padding: 22px 0; color: var(--ink-2); font-size: 13px; }
  .empty-state strong { color: var(--ink); font-weight: 600; }
  .digest-filters { display: flex; flex-wrap: wrap; gap: 6px; padding: 12px 0 4px; }
  .digest-filter { padding: 3px 9px; border: 1px solid var(--line-strong);
                   border-radius: var(--radius-sm); background: var(--surface);
                   color: var(--ink-2); font-size: 12px; }
  .digest-filter:hover { background: var(--bg-hover); color: var(--ink); }
  .digest-filter[aria-pressed="true"] { background: var(--bg-hover); color: var(--ink);
                   border-color: var(--line-strong); font-weight: 600; }
  .digest-filter span { margin-left: 4px; font-family: var(--mono);
                        font-variant-numeric: tabular-nums; color: var(--ink-3); }
  .digest-list { display: grid; }
  .digest-group { margin-top: 22px; }
  .digest-group-head { display: flex; align-items: baseline; gap: 10px;
                       padding-bottom: 6px; border-bottom: 1px solid var(--line); }
  .digest-group-head h3 { margin: 0; font-size: 14px; font-weight: 600; }
  .digest-group-head .quota { color: var(--ink-3); font-size: 11.5px;
                       font-family: var(--mono); font-variant-numeric: tabular-nums; }
  .digest-row { display: grid; grid-template-columns: 26px minmax(0, 1fr) 150px;
                gap: 12px; padding: 11px 0; border-bottom: 1px solid var(--line);
                align-items: start; }
  .digest-row:last-child { border-bottom: none; }
  .article-number { color: var(--ink-3); font-family: var(--mono); font-size: 12px;
                    padding-top: 2px; font-variant-numeric: tabular-nums; }
  .article-copy { min-width: 0; }
  .article-heading { display: flex; align-items: flex-start; gap: 7px; }
  .article-heading h2 { margin: 0; font-size: 14.5px; font-weight: 600;
                        line-height: 1.4; letter-spacing: -0.002em; overflow-wrap: anywhere; }
  .article-heading h2 a:hover { text-decoration: underline; }
  .article-summary { margin: 4px 0 0; color: var(--ink-2); font-size: 12.5px; line-height: 1.55; }
  .digest-meta { display: flex; flex-direction: column; gap: 2px; align-items: flex-start;
                 color: var(--ink-3); font-size: 11.5px; }
  .digest-source { color: var(--ink-2); }
  .digest-time { font-family: var(--mono); font-variant-numeric: tabular-nums; }
  .digest-category { display: none; }
  .digest-state { display: inline-flex; }
  .status-badge { padding: 1px 5px; border-radius: var(--radius-sm); font-size: 10.5px;
                  font-weight: 500; background: var(--pill-new-bg); color: var(--pill-new-ink); }
  .status-updated, .status-breaking { background: var(--pill-upd-bg); color: var(--pill-upd-ink); }
  .filter-empty { color: var(--ink-2); font-size: 12.5px; }
  .digest-gap { margin: 12px 0 0; color: var(--ink-2); font-size: 12.5px;
                padding: 8px 10px; background: var(--bg-soft); border-radius: var(--radius-sm); }

  /* ---------- 简报后更新：待读队列 ---------- */
  .queue-section { margin-top: 34px; }
  .queue-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .queue-head h2 { margin: 0; font-size: 17px; font-weight: 600; }
  .queue-head .queue-meta { color: var(--ink-2); font-size: 12.5px; }
  .queue-list { margin-top: 8px; border-top: 1px solid var(--line); }
  .queue-row { display: grid; grid-template-columns: 22px minmax(0, 1fr) 132px;
               gap: 12px; align-items: start; padding: 9px 0; border-bottom: 1px solid var(--line); }
  .queue-row .rd { margin-top: 2px; }
  .queue-row .q-src { color: var(--ink-2); font-size: 12.5px; min-width: 0;
                      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .queue-row .q-body { min-width: 0; }
  .queue-row .q-title { display: block; font-size: 13.5px; line-height: 1.45;
                        overflow-wrap: anywhere; }
  .queue-row .q-title:hover { text-decoration: underline; }
  .queue-row .q-when { color: var(--ink-3); font-size: 11.5px; text-align: right;
                       font-family: var(--mono); font-variant-numeric: tabular-nums; }
  .queue-row.done .q-title { color: var(--ink-3); text-decoration: line-through; }
  .queue-empty { padding: 16px 0; color: var(--ink-2); font-size: 12.5px; }

  .section-heading { display: flex; flex-wrap: wrap; align-items: baseline;
                     justify-content: space-between; gap: 8px 16px; }
  .analysis-section { margin-top: 34px; }
  .analysis-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                   gap: 14px 20px; margin-top: 12px; }
  .analysis-grid h3 { margin: 0 0 4px; font-size: 12px; color: var(--ink-3);
                      letter-spacing: .04em; font-weight: 600; }
  .analysis-grid p { margin: 0; color: var(--ink-2); font-size: 12.5px; line-height: 1.6; }

  /* 顶栏扩展：搜索、下一轮采集、数据面新鲜度 */
  .command-search { display: flex; align-items: center; gap: 8px; flex: 1 1 320px;
                    max-width: 420px; min-height: 32px; padding: 0 10px;
                    border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
                    background: var(--bg-soft); color: var(--ink-2); font-size: 13px; }
  .command-search:focus-within { border-color: var(--accent-ink); background: var(--surface); }
  .command-search input { flex: 1; min-width: 0; border: 0; background: transparent;
                          color: var(--ink); font: inherit; outline: none; padding: 0; }
  .command-key { font-family: var(--mono); font-size: 11px; color: var(--ink-3);
                 border: 1px solid var(--line); border-radius: var(--radius-sm);
                 padding: 0 4px; background: var(--surface); }
  .chip-clock { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-2);
                font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 12px;
                border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
                padding: 2px 8px; background: var(--bg-soft); }
  .chip-clock .sub { color: var(--ink-3); font-family: var(--font-mono); }
  .pill-live { display: inline-flex; align-items: center; gap: 6px;
               padding: 2px 8px 2px 6px; background: var(--surface);
               border: 1px solid var(--line-strong); border-radius: var(--radius-sm);
               font-size: 12px; color: var(--ink-2); }
  .btn.ghost .ico { font-size: 12px; }
  @media (max-width: 1080px) { .command-search { flex: 1 1 auto; max-width: none; } }
  @media (max-width: 720px) {
    /* The top bar must never wrap: it is sticky, and a second row would change
       the height everything else offsets from.  Phones search from the ledger. */
    .command-search { display: none; }
    .queue-row { grid-template-columns: 22px minmax(0, 1fr); }
    .queue-row .q-when { grid-column: 2; text-align: left; }
    .digest-row { grid-template-columns: 26px minmax(0, 1fr); }
    .digest-meta { grid-column: 2; flex-direction: row; gap: 8px; }
  }

  </style>
</head>
<body>
  <button class="sidebar-scrim" id="sidebar-scrim" type="button" aria-label="关闭导航"></button>
  <div class="app-frame">
__WORKSPACE_SIDEBAR__
    <div class="app-page">
__WORKSPACE_TOPBAR__

<main class="page" id="content">
      <div class="page-meta">
        <div class="who">TR</div>
        <span>数据面 <strong class="mono">__GENERATED_AT__</strong></span>
        <span class="sep">·</span>
        <span id="updatedAt">刚刚刷新</span>
        <span style="flex:1"></span>
        <button class="btn primary" id="reloadBtn" type="button" data-od-id="reload-cta" title="重新载入这一份已发布的快照；页面由采集轮次每 30 分钟重新生成">
          <span class="ico" aria-hidden="true">↻</span><span>刷新快照</span>
        </button>
      </div>

      <h1 class="h" id="overview-title">运行概览</h1>
      <div class="h-sub" id="overviewSub">读数页 · 采集节律、近 7 日入库量与本轮新增与更新；简报与台账在工作台。</div>

          <div class="callout" id="provenance">
            <span class="tag">数据面</span>
            <p>__PROVENANCE__</p>
          </div>

          <div class="kpis" id="kpis"></div>

          <div class="strip" id="cadence">
            <div>
              <div class="k">采集节律</div>
              <div class="v">每 30 分钟 · :00 / :30 <span class="sub">48 轮/日</span></div>
            </div>
            <div>
              <div class="k">下一轮采集</div>
              <div class="v" id="nextCrawlAt">--:-- <span class="sub" id="nextCrawlIn">按 :00 / :30 计算</span></div>
            </div>
            <div>
              <div class="k">简报窗口</div>
              <div class="v">__DIGEST_WINDOW__ <span class="sub" id="nextDigest">下一期 --</span></div>
            </div>
            <div>
              <div class="k">新鲜度窗口</div>
              <div class="v">全局 7 天 <span class="sub">单源 14 / 30 / 90 天覆盖</span></div>
            </div>
          </div>

          <div class="two-col">
            <div class="card">
              <div class="card-title">
                <strong>按发布时间 · 近 7 日入库量</strong>
                <span class="mono" id="sparkSum">—</span>
              </div>
              <svg class="spark" viewBox="0 0 600 150" preserveAspectRatio="none" role="img"
                   aria-label="近 7 日按条目发布时间统计的入库量">
                <g class="spark-grid">
                  <line x1="0" y1="20" x2="600" y2="20"></line>
                  <line x1="0" y1="58" x2="600" y2="58"></line>
                  <line x1="0" y1="96" x2="600" y2="96"></line>
                  <line x1="0" y1="120" x2="600" y2="120"></line>
                </g>
                <path class="spark-fill" id="sparkFill" d=""></path>
                <path class="spark-line" id="sparkLine" d=""></path>
                <g id="sparkDots"></g>
                <g id="sparkValues"></g>
                <g id="sparkLabels" class="spark-axis"></g>
              </svg>
              <div class="card-note" id="sparkNote"></div>
            </div>

            <div class="card">
              <div class="card-title">
                <strong>本轮新增与更新</strong>
                <span class="mono" id="feedCount">—</span>
              </div>
              <div class="feed" id="feed"></div>
            </div>
          </div>

      <footer class="footer">
        <span>数据来源 <span class="key">RSS 聚合快照</span></span>
        <span>·</span>
        <span>页面生成于 <span class="key">__GENERATED_AT__</span> · 北京时间</span>
        <span>·</span>
        <span id="footerTime"></span>
      </footer>
    </main>
  </div>
</div>

<div class="toast" id="toast" role="status" aria-live="polite"></div>
  <script id="homepage-data" type="application/json">__HOMEPAGE_DATA__</script>
__WORKSPACE_SHELL_SCRIPT__

<!-- 工作台运行时 —— 数据来自同行渲染入页的快照，行为一律走真实数据，
     没有模拟采集、没有占位数字。 -->
<script>
(function () {
  'use strict';
  var PAGE_SIZE = 40;                 /* 每次载入的台账行数 */
  var STATE_LABEL = { 0: '既有', 1: '新增', 2: '实质更新' };
  var STATE_CLASS = { 0: 'old', 1: 'new', 2: 'upd' };

  var $ = function (id) { return document.getElementById(id); };

  /* localStorage 在无同源上下文的预览沙箱里会在属性访问时抛 SecurityError，
     整页脚本会因此中止（页面只剩静态骨架）。探测一次，失败退回内存存储。 */
  var LS = (function () {
    try {
      window.localStorage.setItem('__probe__', '1');
      window.localStorage.removeItem('__probe__');
      return window.localStorage;
    } catch (_) {
      var m = {};
      return { getItem: function (k) { return Object.prototype.hasOwnProperty.call(m, k) ? m[k] : null; },
               setItem: function (k, v) { m[k] = String(v); },
               removeItem: function (k) { delete m[k]; } };
    }
  })();

  function parseData() {
    var node = $('homepage-data');
    var data = { updates: [], allNews: [], categories: [], sources: [] };
    try { data = JSON.parse(node.textContent || '{}') || data; } catch (_) {}
    data.allNews = data.allNews || [];
    data.sources = data.sources || [];
    data.categories = data.categories || [];
    /* source/category names ship as lookup indices; resolve once, here. */
    data.allNews.forEach(function (item) {
      if (typeof item._si === 'number') item.source_name = data.sources[item._si] || item.source_name;
      if (typeof item._ci === 'number') item.category_name = data.categories[item._ci] || item.category_name;
    });
    return data;
  }
  var DATA = parseData();

  /* 状态编码沿用引擎的判定：updated = 同一链接标题发生变更（engine.py:290），
     new = 最近一期简报之后首次出现；breaking 是仍在突发窗口内的 new/updated，
     台账里按“新增”归并，突发条另有顶栏提示。 */
  function stateOf(status) {
    if (status === 'updated') return 2;
    if (status === 'new' || status === 'breaking') return 1;
    return 0;
  }
  var items = DATA.allNews.map(function (r, i) {
    return {
      i: i,
      t: String(r.title || ''),
      u: String(r.url || ''),
      p: String(r.published_at || ''),
      c: String(r.category_name || '其他重要新闻'),
      s: String(r.source_name || 'RSS'),
      k: stateOf(String(r.status || '')),
      when: r.published_at ? new Date(String(r.published_at).replace(' ', 'T')) : null,
      q: false                                /* 是否属于“简报后更新” */
    };
  });
  (DATA.updates || []).forEach(function (index) {
    if (typeof index === 'number' && items[index]) items[index].q = true;
  });

  var SUMS = [];
  try {
    var sumsNode = $('summaries-data');
    SUMS = sumsNode ? (JSON.parse(sumsNode.textContent || '[]') || []) : [];
  } catch (_) {}
  var SUMMARIES_URL = '__SUMMARIES_FILENAME__';

  var readKey = 'trendradar.read.v1';
  var read = {};
  try { (JSON.parse(LS.getItem(readKey) || '[]') || []).forEach(function (i) { read[i] = true; }); } catch (_) {}
  var autoOn = LS.getItem('trendradar.auto') === 'true';
  var autoTimer = null;
  var busy = false;
  var loaded = PAGE_SIZE;
  var lastRefresh = new Date();

  var SNAPSHOT_AT = (function () {
    var raw = String(DATA.generatedAt || '');
    var d = raw ? new Date(raw.replace(' ', 'T')) : null;
    return d && !isNaN(d.getTime()) ? d : null;
  })();
  var STALE_AFTER_MS = Number(DATA.staleAfter || 90) * 60000;
  var REFRESH_SECONDS = Number(DATA.refreshSeconds || 1800);
  var NEXT_RUN = DATA.nextRun || null;

  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function reduceMotion() {
    return typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function fmtWhen(d) {
    return d && !isNaN(d.getTime())
      ? pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes())
      : '—';
  }
  function timeAgo(d) {
    var s = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
    if (s < 60) return s + ' 秒前';
    var m = Math.floor(s / 60);
    if (m < 60) return m + ' 分钟前';
    var h = Math.floor(m / 60);
    if (h < 24) return h + ' 小时前';
    return Math.floor(h / 24) + ' 天前';
  }
  /* 来源名 → 稳定色（oklch，45% 亮度保证白字 ≥4.5:1） */
  function srcColor(name) {
    var h = 0;
    for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
    return 'oklch(45% 0.11 ' + h + ')';
  }
  function srcInitial(name) {
    if (/^[A-Za-z0-9 .&'-]+$/.test(name)) {
      return name.split(/\s+/).map(function (w) { return w[0]; }).join('').slice(0, 2).toUpperCase();
    }
    return name.slice(0, 2);
  }

  /* ---------------- KPI ---------------- */
  function countNew() { return items.filter(function (x) { return x.k === 1; }).length; }
  function countUpd() { return items.filter(function (x) { return x.k === 2; }).length; }
  function queue() { return items.filter(function (x) { return x.q; }); }
  function countUnread() { return queue().filter(function (x) { return !read[x.i]; }).length; }
  function spreadOf(list) { return new Set(list.map(function (x) { return x.s; })).size; }
  function missingTime() { return items.filter(function (x) { return !x.when || isNaN(x.when.getTime()); }).length; }

  var KPI_DEFS = [
    { id: 'kTotal', label: '台账条目', get: function () { return items.length; },
      delta: function () { return '来自 ' + DATA.sources.length + ' 个来源 · ' + DATA.categories.length + ' 个板块'; } },
    { id: 'kNew', label: '本期新增', get: countNew,
      delta: function () {
        var fresh = items.filter(function (x) { return x.k === 1; });
        return '最近一期简报之后首次出现 · 覆盖 ' + spreadOf(fresh) + ' 个来源';
      } },
    { id: 'kUpd', label: '实质更新', get: countUpd,
      delta: function () { return '同一链接标题发生变更 · 来自 ' + spreadOf(items.filter(function (x) { return x.k === 2; })) + ' 个来源'; } },
    { id: 'kUnread', label: '待读', get: countUnread,
      delta: function () { var n = queue().length; return '简报后更新 ' + n + ' 条 · 已读 ' + (n - countUnread()); } }
  ];
  function tweenText(el, from, to, ms) {
    ms = ms || 500;
    if (from === to || reduceMotion()) { el.textContent = String(to); return; }
    var start = performance.now();
    (function step(now) {
      var t = Math.min(1, (now - start) / ms);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = String(Math.round(from + (to - from) * eased));
      if (t < 1) requestAnimationFrame(step);
    })(start);
  }
  function renderKpi(keep) {
    var wrap = $('kpis');
    if (!wrap.children.length) {
      wrap.innerHTML = KPI_DEFS.map(function (d) {
        return '<div class="kpi"><div class="label">' + esc(d.label) + '</div>'
          + '<div class="value" id="' + esc(d.id) + '">' + d.get() + '</div>'
          + '<div class="delta" id="' + esc(d.id) + 'D">' + esc(d.delta()) + '</div></div>';
      }).join('');
      return;
    }
    KPI_DEFS.forEach(function (d) {
      var cell = $(d.id), dl = $(d.id + 'D');
      if (!cell) return;
      var after = d.get();
      if (keep) { tweenText(cell, Number(cell.textContent), after); }
      else { cell.textContent = String(after); }
      if (dl) dl.textContent = d.delta();
    });
  }

  /* ---------------- 近 7 日入库量 ---------------- */
  function dailySeries() {
    var days = [];
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    for (var back = 6; back >= 0; back--) {
      days.push(new Date(today.getTime() - back * 864e5));
    }
    var buckets = days.map(function (d) {
      return { key: pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()), n: 0, t: d.getTime() };
    });
    var older = 0, future = 0;
    items.forEach(function (x) {
      if (!x.when || isNaN(x.when.getTime())) return;
      var day = new Date(x.when.getTime());
      day.setHours(0, 0, 0, 0);
      var hit = null;
      for (var i = 0; i < buckets.length; i++) { if (buckets[i].t === day.getTime()) { hit = buckets[i]; break; } }
      if (hit) hit.n += 1;
      else if (day.getTime() > buckets[buckets.length - 1].t) future += 1;
      else older += 1;
    });
    return { buckets: buckets, older: older, future: future };
  }
  function renderSpark() {
    var s = dailySeries();
    var W = 600, H = 150, padL = 26, padR = 18, padT = 18, padB = 30;
    var series = s.buckets.map(function (b) { return b.n; });
    var labels = s.buckets.map(function (b) { return b.key; });
    var max = Math.max.apply(null, series.concat([1]));
    var stepX = (W - padL - padR) / (series.length - 1);
    function y(v) { return padT + (1 - v / (max * 1.15)) * (H - padT - padB); }
    var pts = series.map(function (v, i) { return [padL + i * stepX, y(v)]; });
    var line = 'M ' + pts.map(function (p) { return p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join(' L ');
    $('sparkLine').setAttribute('d', line);
    $('sparkFill').setAttribute('d', line + ' L ' + pts[pts.length - 1][0].toFixed(1) + ' ' + (H - padB)
      + ' L ' + pts[0][0].toFixed(1) + ' ' + (H - padB) + ' Z');
    $('sparkDots').innerHTML = pts.map(function (p) {
      return '<circle class="spark-dot" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="2.6"></circle>';
    }).join('');
    $('sparkValues').innerHTML = pts.map(function (p, i) {
      return '<text class="spark-val" x="' + p[0].toFixed(1) + '" y="' + (p[1] - 8).toFixed(1)
        + '" text-anchor="middle">' + series[i] + '</text>';
    }).join('');
    $('sparkLabels').innerHTML = labels.map(function (d, i) {
      return '<text x="' + (padL + i * stepX).toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle">' + d + '</text>';
    }).join('');
    var total = series.reduce(function (a, b) { return a + b; }, 0);
    $('sparkSum').textContent = total + ' 条';
    var missing = missingTime();
    var note = '按条目发布时间分箱，近 7 日共 ' + total + ' 条；另有 ' + s.older + ' 条早于窗口、'
      + missing + ' 条没有发布时间';
    if (s.future) note += '、' + s.future + ' 条源给出的时间晚于快照日';
    note += '。末段为不完整日。发布时间由 RSS 提供，不是采集时间。';
    $('sparkNote').textContent = note;
  }

  /* ---------------- 本轮新增与更新 ---------------- */
  function renderFeed() {
    var pool = items.filter(function (x) { return x.k !== 0; })
      .sort(function (a, b) {
        return (b.when && !isNaN(b.when.getTime()) ? b.when.getTime() : -1)
             - (a.when && !isNaN(a.when.getTime()) ? a.when.getTime() : -1);
      });
    var show = pool.slice(0, 8);
    $('feed').innerHTML = show.length ? show.map(function (it) {
      return '<div class="feed-row">'
        + '<span class="av" style="background:' + esc(srcColor(it.s)) + '">' + esc(srcInitial(it.s)) + '</span>'
        + '<div class="body"><span class="who">' + esc(it.s) + '</span>'
        + '<span class="mono" style="font-size:11px;color:var(--ink-2)"> ' + STATE_LABEL[it.k] + '</span>'
        + '<a class="t" href="' + esc(it.u) + '" target="_blank" rel="noopener noreferrer"'
        + (it.u ? '' : ' aria-disabled="true"') + '>' + esc(it.t) + '</a></div>'
        + '<div class="time">' + esc(fmtWhen(it.when)) + '</div></div>';
    }).join('') : '<div class="empty">最近一期简报之后没有新增或实质更新的条目。</div>';
    $('feedCount').textContent = pool.length + ' 条 · 显示最近 ' + show.length;
  }

  /* ---------------- 顶栏：下一轮采集 / 新鲜度 ---------------- */
  function tickClock() {
    var now = new Date();
    var next = NEXT_RUN ? new Date(String(NEXT_RUN).replace(' ', 'T')) : null;
    if (!next || isNaN(next.getTime())) {
      var toHalf = (30 - (now.getMinutes() % 30)) * 60 - now.getSeconds();
      next = new Date(now.getTime() + toHalf * 1000);
    }
    var left = Math.max(0, Math.floor((next.getTime() - now.getTime()) / 1000));
    var clock = pad2(next.getHours()) + ':' + pad2(next.getMinutes());
    var away = '（' + Math.floor(left / 60) + ' 分 ' + pad2(left % 60) + ' 秒后）';
    var chip = $('nextCrawl');            /* 顶栏 */
    if (chip) chip.textContent = clock;
    var cell = $('nextCrawlAt');          /* 节律条 */
    if (cell) cell.textContent = clock + ' ';
    var cellIn = $('nextCrawlIn');
    if (cellIn) cellIn.textContent = away;
    var slots = [[8, 0], [12, 30], [20, 0]];
    var up = slots.map(function (t) {
      return { t: t, d: new Date(now.getFullYear(), now.getMonth(), now.getDate(), t[0], t[1]) };
    }).filter(function (o) { return o.d > now; });
    /* After 20:00 the next issue is tomorrow's 08:00 — not "24 hours from now". */
    var nd = up.length
      ? up[0]
      : { t: [8, 0], d: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 8, 0) };
    var ndCell = $('nextDigest');
    if (ndCell) ndCell.textContent = '下一期 ' + pad2(nd.t[0]) + ':' + pad2(nd.t[1])
      + '（' + Math.max(1, Math.round((nd.d - now) / 3600000)) + ' 小时后）';
  }
  function updateTimes() {
    var live = $('liveText'), pill = $('livePill');
    $('updatedAt').textContent = '最后刷新 ' + timeAgo(lastRefresh);
    $('footerTime').textContent = '本页刷新于 ' + lastRefresh.toLocaleTimeString('zh-CN', { hour12: false });
    var stale = SNAPSHOT_AT ? (Date.now() - SNAPSHOT_AT.getTime()) > STALE_AFTER_MS : false;
    if (pill) pill.classList.toggle('stale', stale);
    if (live && !busy) {
      live.textContent = !SNAPSHOT_AT ? '数据面时间未知'
        : stale ? '陈旧 · 数据面 ' + timeAgo(SNAPSHOT_AT) : '数据面 · ' + timeAgo(SNAPSHOT_AT);
    }
  }

  function showToast(msg) {
    var t = $('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () { t.classList.remove('show'); }, 2200);
  }
  function reloadPage(msg) {
    if (busy) return;
    busy = true;
    if ($('refreshIco')) $('refreshIco').classList.add('spin');
    if (msg) showToast(msg);
    setTimeout(function () { window.location.reload(); }, 220);
  }
  /* ---------------- 起手：读数页只渲染读数 ---------------- */
  renderKpi(false); renderSpark(); renderFeed(); tickClock(); updateTimes();
  setInterval(updateTimes, 5000);
  setInterval(tickClock, 1000);
  /* 不接台账与队列：刷新就是重读这一份已发布的快照。 */
  var reloadBtn = $('reloadBtn');
  if (reloadBtn) reloadBtn.addEventListener('click', function () { reloadPage('正在重读这一份快照…'); });
})();
</script>

</body>
</html>
'''
