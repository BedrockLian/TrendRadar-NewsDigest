# coding=utf-8
"""Render the self-contained public news workspace."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from trendradar.digest import HomepageSnapshot
from trendradar.digest.engine import safe_http_url
from trendradar.report.helpers import html_escape


_DEFAULT_SLOTS = [
    {"key": "morning_digest", "name": "早间新闻简报", "start": "08:00"},
    {"key": "noon_digest", "name": "午间新闻简报", "start": "12:30"},
    {"key": "evening_digest", "name": "晚间新闻简报", "start": "20:00"},
]


def _safe_json_data(value: Any) -> str:
    """Serialize JSON safely inside an HTML raw-text script element."""
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _display_time(value: str, pattern: str = "%m-%d %H:%M") -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime(pattern)
    except (TypeError, ValueError):
        return str(value)


def _external_link(url: str, text: str) -> str:
    safe_url = safe_http_url(str(url or ""))
    label = html_escape(str(text or ""))
    if not safe_url:
        return label
    return f'<a href="{html_escape(safe_url)}" target="_blank" rel="noopener noreferrer">{label}</a>'


def _safe_archive_url(url: str) -> str:
    value = str(url or "")
    if value.startswith("briefings/") and ".." not in value and "\\" not in value:
        return value
    return safe_http_url(value)


def _public_item(item: Dict[str, Any]) -> Dict[str, str]:
    """Keep only fields needed by the browser renderer."""
    return {
        "title": str(item.get("title") or ""),
        "url": safe_http_url(str(item.get("url") or "")),
        "summary": str(item.get("summary") or ""),
        "source_name": str(item.get("source_name") or "RSS"),
        "published_at": str(item.get("published_at") or ""),
        "category_id": str(item.get("category_id") or "other"),
        "category_name": str(item.get("category_name") or "其他重要新闻"),
        "status": str(item.get("status") or ""),
    }


def _legacy_items(rss_items: Optional[List[Dict]]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for stat in rss_items or []:
        category = str(stat.get("word") or "其他重要新闻")
        for item in stat.get("titles", []):
            items.append({
                "title": str(item.get("title") or ""),
                "url": safe_http_url(str(item.get("url") or "")),
                "summary": str(item.get("summary") or ""),
                "source_name": str(item.get("source_name") or "RSS"),
                "published_at": str(item.get("time_display") or ""),
                "category_id": "other",
                "category_name": category,
                "status": "new" if item.get("is_new") else "",
            })
    return items


def _render_alerts(snapshot: Optional[HomepageSnapshot]) -> str:
    if not snapshot or not snapshot.active_alerts:
        return ""
    links = [_external_link(item.get("url", ""), item.get("title", "")) for item in snapshot.active_alerts[:3]]
    return (
        '<aside class="alert-strip" id="alerts" aria-label="突发新闻">'
        '<span class="alert-label">突发</span><div class="alert-items">'
        + '<span aria-hidden="true">·</span>'.join(links)
        + "</div></aside>"
    )


def _render_slots(snapshot: Optional[HomepageSnapshot]) -> str:
    slots = list(snapshot.slots) if snapshot and snapshot.slots else list(_DEFAULT_SLOTS)
    latest_key = snapshot.latest_digest.period_key if snapshot and snapshot.latest_digest else ""
    parts = []
    for slot in slots:
        classes = ["slot"]
        if slot.get("key") == latest_key:
            classes.append("published")
        if slot.get("active"):
            classes.append("active")
        if slot.get("next"):
            classes.append("next")
        parts.append(
            f'<div class="{" ".join(classes)}" data-slot="{html_escape(str(slot.get("key") or ""))}">'
            f'<time>{html_escape(str(slot.get("start") or ""))}</time>'
            f'<span>{html_escape(str(slot.get("name") or "").replace("新闻简报", ""))}</span></div>'
        )
    return '<div class="edition-rail" aria-label="每日发刊时间">' + "".join(parts) + "</div>"


def _render_digest(
    snapshot: Optional[HomepageSnapshot], fallback_current_count: int = 0
) -> str:
    digest = snapshot.latest_digest if snapshot else None
    if not digest:
        next_time = str((snapshot.next_slot if snapshot else {}).get("start") or "08:00")
        current_count = len(snapshot.all_news) if snapshot else fallback_current_count
        return f'''<section class="digest-section" id="digest" aria-labelledby="digest-title">
  <div class="edition-heading empty-heading"><div><p class="section-kicker">最新一期</p><h1 id="digest-title">首期简报正在准备</h1></div><p class="edition-ledger">已采集 {current_count} 篇</p></div>
  <div class="empty-state"><strong>首期简报将在 {html_escape(next_time)} 生成</strong><span>生成前可在“全部新闻”浏览本轮抓取内容。</span></div>
</section>'''

    archive_url = _safe_archive_url(digest.archive_url)
    download = (
        f'<a id="digest-download" class="download-link" href="{html_escape(archive_url)}" download>下载 Markdown <span aria-hidden="true">↓</span></a>'
        if archive_url else ""
    )
    filters = [f'<button class="digest-filter" type="button" data-category="all" aria-pressed="true">全部 <span>{digest.article_count}</span></button>']
    rows = []
    index = 0
    for section in digest.sections:
        category = str(section.get("name") or "其他重要新闻")
        count = int(section.get("count") or 0)
        filters.append(
            f'<button class="digest-filter" type="button" data-category="{html_escape(category)}" aria-pressed="false"'
            f'{" disabled" if count == 0 else ""}>{html_escape(category)} <span>{count}</span></button>'
        )
        for item in section.get("articles", []):
            index += 1
            status = str(item.get("status") or "")
            status_label = "突发" if status in {"breaking", "突发"} else "更新" if status in {"updated", "更新"} else ""
            badge = f'<span class="status-badge status-{html_escape(status)}">{status_label}</span>' if status_label else ""
            summary = f'<p class="article-summary">{html_escape(str(item.get("summary") or ""))}</p>' if item.get("summary") else ""
            published = str(item.get("published_at") or "")
            time_html = f'<time datetime="{html_escape(published)}">{html_escape(_display_time(published))}</time>' if published else ""
            separator = '<span aria-hidden="true">·</span>' if time_html else ""
            rows.append(
                f'<article class="digest-row" data-category="{html_escape(category)}"><span class="article-number" aria-hidden="true">{index:02d}</span>'
                f'<div class="article-copy"><div class="article-heading"><h2>{_external_link(item.get("url", ""), item.get("title", ""))}</h2>{badge}</div>{summary}'
                f'<p class="article-meta"><span>{html_escape(str(item.get("source_name") or "RSS"))}</span>{separator}{time_html}</p></div></article>'
            )
    created_date = _display_time(digest.created_at, "%Y-%m-%d")
    created_time = _display_time(digest.created_at, "%H:%M")
    return f'''<section class="digest-section" id="digest" aria-labelledby="digest-title">
  <div class="edition-heading"><div><p class="section-kicker">{html_escape(created_date)} · 最新一期</p><h1 id="digest-title">{html_escape(digest.period_name or "新闻简报")}</h1></div>
  <div class="edition-actions"><p class="edition-ledger">{digest.article_count} 篇 · {digest.source_count} 个来源 · {html_escape(created_time)} 发布</p>{download}</div></div>
  <div class="digest-filters" aria-label="筛选本期分类">{"".join(filters)}</div><div class="digest-list">{"".join(rows)}</div>
  <p class="filter-empty" id="digest-filter-empty" hidden>本期该分类没有新闻。</p>
</section>'''


def _render_ai_analysis(ai_analysis: Optional[Any]) -> str:
    if not ai_analysis or not getattr(ai_analysis, "success", False):
        return ""
    labels = [
        ("核心趋势", getattr(ai_analysis, "core_trends", "")),
        ("舆论与争议", getattr(ai_analysis, "sentiment_controversy", "")),
        ("变化信号", getattr(ai_analysis, "signals", "")),
        ("RSS 洞察", getattr(ai_analysis, "rss_insights", "")),
        ("后续观察", getattr(ai_analysis, "outlook_strategy", "")),
    ]
    blocks = [f'<article><h3>{html_escape(label)}</h3><p>{html_escape(str(content))}</p></article>' for label, content in labels if content]
    if not blocks:
        return ""
    return '<section class="analysis-section" id="analysis" aria-labelledby="analysis-title"><div class="section-heading"><div><p class="section-kicker">分析</p><h2 id="analysis-title">本期观察</h2></div></div><div class="analysis-grid">' + "".join(blocks) + "</div></section>"


def render_html_content(
    report_data: Dict,
    total_titles: int,
    mode: str = "daily",
    update_info: Optional[Dict] = None,
    *,
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[List[Dict]] = None,
    rss_new_items: Optional[List[Dict]] = None,
    display_mode: str = "keyword",
    standalone_data: Optional[Dict] = None,
    ai_analysis: Optional[Any] = None,
    show_new_section: bool = True,
    homepage_snapshot: Optional[HomepageSnapshot] = None,
) -> str:
    """Render one dependency-free, responsive HTML document."""
    now = get_time_func() if get_time_func else datetime.now().astimezone()
    current_items = [_public_item(item) for item in homepage_snapshot.all_news] if homepage_snapshot else _legacy_items(rss_items)
    update_items = [_public_item(item) for item in homepage_snapshot.updates_since_digest] if homepage_snapshot else []
    categories: List[str] = []
    if homepage_snapshot and homepage_snapshot.latest_digest:
        categories.extend(str(section.get("name") or "其他重要新闻") for section in homepage_snapshot.latest_digest.sections)
    categories.extend(item["category_name"] for item in current_items)
    categories = list(dict.fromkeys(categories))
    payload = _safe_json_data({"updates": update_items, "allNews": current_items, "categories": categories})
    generated = _display_time(homepage_snapshot.generated_at if homepage_snapshot else now.isoformat(), "%Y-%m-%d %H:%M")
    replacements = {
        "__ALERTS__": _render_alerts(homepage_snapshot),
        "__SLOTS__": _render_slots(homepage_snapshot),
        "__DIGEST__": _render_digest(homepage_snapshot, len(current_items)),
        "__AI_ANALYSIS__": _render_ai_analysis(ai_analysis),
        "__UPDATES_HIDDEN__": "" if update_items else " hidden",
        "__UPDATE_COUNT__": str(len(update_items)),
        "__TOTAL_COUNT__": str(len(current_items)),
        "__SOURCE_COUNT__": str(len({item["source_name"] for item in current_items if item["source_name"]})),
        "__CATEGORY_OPTIONS__": "".join(f'<option value="{html_escape(category)}">{html_escape(category)}</option>' for category in categories),
        "__HOMEPAGE_DATA__": payload,
        "__GENERATED_AT__": html_escape(generated),
    }
    document = _DOCUMENT
    for marker, value in replacements.items():
        document = document.replace(marker, value)
    return document


_DOCUMENT = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#F4F2EC">
  <title>热点新闻分析 · TrendRadar</title>
  <script>
    try {
      var storedTheme = localStorage.getItem('trendradar-theme');
      if (storedTheme === 'dark' || (!storedTheme && matchMedia('(prefers-color-scheme: dark)').matches)) document.documentElement.dataset.theme = 'dark';
    } catch (_) {}
  </script>
  <style>
    :root {
      color-scheme: light; --paper: #F4F2EC; --ink: #182128; --surface: #FFFEFA;
      --signal: #C43D32; --category: #2F6C70; --rule: #D6D2C8; --muted: #667078;
      --soft: #E9E6DE; --shadow: rgba(24, 33, 40, .07);
      --display: ui-serif, "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", SimSun, serif;
      --body: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
      --utility: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
    }
    :root[data-theme="dark"] {
      color-scheme: dark; --paper: #11171B; --ink: #ECE9E1; --surface: #182126;
      --signal: #EF6A5B; --category: #73B6B1; --rule: #354047; --muted: #ABB2B5;
      --soft: #202B30; --shadow: rgba(0, 0, 0, .18);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; scroll-padding-top: 112px; }
    body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--body); line-height: 1.55; text-rendering: optimizeLegibility; }
    button, input, select { font: inherit; }
    a { color: inherit; text-decoration-thickness: 1px; text-underline-offset: .18em; }
    a:hover { color: var(--signal); }
    :focus-visible { outline: 3px solid var(--category); outline-offset: 3px; }
    [hidden] { display: none !important; }
    .site-header { position: sticky; top: 0; z-index: 20; background: var(--paper); border-bottom: 1px solid var(--rule); }
    .header-row { width: min(1180px, calc(100% - 40px)); min-height: 64px; margin: 0 auto; display: flex; align-items: center; gap: 32px; }
    .wordmark { flex: 0 0 auto; font: 700 1.08rem var(--display); letter-spacing: .02em; text-decoration: none; }
    .wordmark-mark { color: var(--signal); }
    .primary-nav { display: flex; align-items: center; gap: 24px; min-width: 0; font-size: .9rem; }
    .primary-nav a { text-decoration: none; white-space: nowrap; }
    .primary-nav a:hover { text-decoration: underline; }
    .header-tools { margin-left: auto; display: flex; align-items: center; gap: 8px; }
    .tool-button { border: 0; background: transparent; color: var(--muted); padding: 8px 10px; border-radius: 3px; cursor: pointer; }
    .tool-button:hover { color: var(--ink); background: var(--soft); }
    .alert-strip { background: var(--signal); color: #fff; display: flex; gap: 16px; padding: 9px max(20px, calc((100vw - 1180px) / 2)); font-size: .86rem; }
    .alert-label { font: 700 .8rem var(--utility); letter-spacing: .08em; }
    .alert-items { display: flex; flex-wrap: wrap; gap: 10px; min-width: 0; }
    .alert-items a { text-decoration: none; }
    .alert-items a:hover { color: #fff; text-decoration: underline; }
    .edition-rail { width: min(1180px, calc(100% - 40px)); margin: 0 auto; display: grid; grid-template-columns: repeat(3, 1fr); padding: 18px 0 22px; }
    .slot { position: relative; display: flex; align-items: baseline; gap: 9px; border-top: 1px solid var(--rule); padding-top: 10px; color: var(--muted); }
    .slot::before { content: ""; position: absolute; width: 7px; height: 7px; top: -4px; left: 0; border-radius: 50%; background: var(--rule); }
    .slot:not(:last-child) { padding-right: 22px; }
    .slot.published, .slot.active { color: var(--ink); border-top-color: var(--ink); }
    .slot.published::before { background: var(--signal); box-shadow: 0 0 0 4px color-mix(in srgb, var(--signal) 14%, transparent); }
    .slot.next::after { content: "下一期"; margin-left: auto; font: .65rem var(--utility); color: var(--category); }
    .slot time { font: .82rem var(--utility); }
    .slot span { font-size: .78rem; }
    main { width: min(1180px, calc(100% - 40px)); margin: 0 auto 80px; background: var(--surface); box-shadow: 0 18px 50px var(--shadow); border: 1px solid var(--rule); }
    main > section { padding: 52px 64px; }
    main > section + section { border-top: 1px solid var(--rule); }
    .edition-heading, .section-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; margin-bottom: 24px; }
    .section-kicker { margin: 0 0 7px; font: .72rem var(--utility); color: var(--category); letter-spacing: .08em; text-transform: uppercase; }
    h1, .section-heading h2 { margin: 0; font-family: var(--display); font-weight: 700; letter-spacing: -.025em; }
    h1 { font-size: clamp(2.25rem, 5vw, 4.6rem); line-height: 1.03; }
    .section-heading h2 { font-size: clamp(1.8rem, 3vw, 2.7rem); line-height: 1.1; }
    .edition-actions { display: grid; justify-items: end; gap: 9px; }
    .edition-ledger { margin: 0; color: var(--muted); font: .75rem var(--utility); white-space: nowrap; }
    .download-link { color: var(--category); font-size: .8rem; }
    .digest-filters { display: flex; gap: 7px; overflow-x: auto; scrollbar-width: thin; padding: 3px 3px 14px; margin: 0 -3px 4px; }
    .digest-filter { flex: 0 0 auto; border: 1px solid var(--rule); background: transparent; color: var(--muted); border-radius: 999px; padding: 7px 11px; font-size: .76rem; cursor: pointer; }
    .digest-filter span { font-family: var(--utility); margin-left: 3px; }
    .digest-filter[aria-pressed="true"] { background: var(--ink); border-color: var(--ink); color: var(--surface); }
    .digest-filter:disabled { opacity: .48; cursor: default; }
    .digest-row, .news-row { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 18px; padding: 24px 0; border-top: 1px solid var(--rule); }
    .article-number { font: .76rem var(--utility); color: var(--signal); padding-top: 7px; }
    .article-heading { display: flex; align-items: flex-start; gap: 14px; }
    .article-heading h2, .news-row h3 { margin: 0; font-family: var(--display); font-size: clamp(1.2rem, 2vw, 1.48rem); line-height: 1.38; font-weight: 650; overflow-wrap: anywhere; }
    .article-heading a, .news-row h3 a { text-decoration: none; }
    .article-heading a:hover, .news-row h3 a:hover { text-decoration: underline; }
    .status-badge { flex: 0 0 auto; margin-top: 4px; padding: 2px 6px; border: 1px solid currentColor; color: var(--category); font: .65rem/1.4 var(--utility); }
    .status-突发, .status-breaking { color: var(--signal); }
    .article-summary { max-width: 820px; margin: 9px 0 0; color: var(--muted); font-size: .94rem; }
    .article-meta { display: flex; flex-wrap: wrap; gap: 7px; margin: 10px 0 0; color: var(--muted); font: .7rem var(--utility); }
    .empty-state { min-height: 230px; display: grid; place-content: center; justify-items: center; gap: 7px; border-top: 1px solid var(--rule); color: var(--muted); text-align: center; }
    .empty-state strong { color: var(--ink); font: 700 1.25rem var(--display); }
    .analysis-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 44px; border-top: 1px solid var(--rule); }
    .analysis-grid article { padding: 24px 0; border-bottom: 1px solid var(--rule); }
    .analysis-grid h3 { margin: 0 0 8px; font: 700 .78rem var(--utility); color: var(--category); }
    .analysis-grid p { margin: 0; white-space: pre-line; font-size: .92rem; }
    .updates-intro, .all-news-ledger { margin: 0; color: var(--muted); font: .73rem var(--utility); }
    .updates-list, .all-news-list { border-bottom: 1px solid var(--rule); }
    .news-row { grid-template-columns: 54px minmax(0, 1fr) 150px; }
    .news-row .article-copy { min-width: 0; }
    .news-row-side { text-align: right; color: var(--muted); font: .68rem var(--utility); padding-top: 5px; }
    .news-row-side span, .news-row-side time { display: block; }
    .news-category-label { color: var(--category); margin-top: 5px; }
    .news-controls { display: grid; grid-template-columns: minmax(220px, 2fr) repeat(3, minmax(130px, 1fr)); gap: 10px; margin: 24px 0 14px; }
    .control { display: grid; gap: 5px; }
    .control span { color: var(--muted); font: .66rem var(--utility); }
    .control input, .control select { width: 100%; min-width: 0; border: 1px solid var(--rule); background: var(--surface); color: var(--ink); border-radius: 3px; padding: 10px 11px; font-size: .84rem; }
    .results-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 12px 0; }
    #results-count { margin: 0; color: var(--muted); font-size: .78rem; }
    .reset-button, .load-more { border: 1px solid var(--rule); background: transparent; color: var(--ink); border-radius: 3px; cursor: pointer; padding: 8px 12px; font-size: .76rem; }
    .reset-button:hover, .load-more:hover { border-color: var(--category); color: var(--category); }
    .load-more { display: block; margin: 24px auto 0; min-width: 140px; }
    .filter-empty { color: var(--muted); text-align: center; padding: 36px 0 16px; }
    .site-footer { width: min(1180px, calc(100% - 40px)); margin: -52px auto 30px; display: flex; justify-content: space-between; color: var(--muted); font: .68rem var(--utility); }
    @media (max-width: 820px) {
      html { scroll-padding-top: 152px; }
      .header-row { width: 100%; min-height: auto; padding: 12px 16px 0; flex-wrap: wrap; gap: 8px 16px; }
      .wordmark { order: 1; } .header-tools { order: 2; }
      .primary-nav { order: 3; width: calc(100% + 32px); margin: 0 -16px; padding: 8px 16px 11px; overflow-x: auto; gap: 20px; border-top: 1px solid var(--rule); }
      .alert-strip { padding: 9px 16px; }
      .edition-rail { width: calc(100% - 32px); padding: 15px 0 18px; }
      .slot { display: grid; gap: 2px; } .slot.next::after { content: none; }
      main { width: 100%; margin-bottom: 64px; border-left: 0; border-right: 0; box-shadow: none; }
      main > section { padding: 38px 20px; }
      .edition-heading, .section-heading { align-items: flex-start; flex-direction: column; gap: 12px; margin-bottom: 20px; }
      .edition-actions { justify-items: start; }
      h1 { font-size: clamp(2rem, 12vw, 3.2rem); }
      .digest-row, .news-row { grid-template-columns: 34px minmax(0, 1fr); gap: 10px; padding: 20px 0; }
      .article-number { padding-top: 5px; } .article-heading { gap: 8px; }
      .article-heading h2, .news-row h3 { font-size: 1.08rem; line-height: 1.43; }
      .news-row-side { grid-column: 2; text-align: left; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
      .news-row-side span, .news-row-side time { display: inline; }
      .news-category-label { margin: 0; }
      .news-controls { grid-template-columns: 1fr 1fr; }
      .control-search { grid-column: 1 / -1; }
      .analysis-grid { grid-template-columns: 1fr; }
      .site-footer { width: calc(100% - 32px); margin-top: -44px; }
    }
    @media (max-width: 480px) {
      .tool-button { padding: 7px 8px; font-size: .8rem; }
      .edition-ledger { white-space: normal; }
      main > section { padding: 32px 16px; }
      .news-controls { grid-template-columns: 1fr; } .control-search { grid-column: auto; }
      .results-toolbar { align-items: flex-start; }
      .alert-items { display: grid; gap: 4px; } .alert-items > span { display: none; }
      .site-footer { display: grid; gap: 5px; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
    }
    @media print {
      .site-header, .alert-strip, .edition-rail, #updates, #all-news, .site-footer, .digest-filters { display: none !important; }
      body, main { background: #fff; color: #000; }
      main { width: 100%; border: 0; box-shadow: none; }
      .digest-row { break-inside: avoid; }
    }
  </style>
</head>
<body>
  <header class="site-header">
    <div class="header-row">
      <a class="wordmark" href="#digest"><span class="wordmark-mark">●</span> TrendRadar</a>
      <nav class="primary-nav" aria-label="主导航">
        <a href="#digest">最新一期</a>
        <a id="updates-nav" href="#updates"__UPDATES_HIDDEN__>简报后更新</a>
        <a href="#all-news">全部新闻</a>
        <a href="briefings/">简报存档</a>
      </nav>
      <div class="header-tools">
        <button class="tool-button" id="search-jump" type="button">搜索</button>
        <button class="tool-button" id="theme-toggle" type="button" aria-pressed="false">暗色</button>
      </div>
    </div>
  </header>
  __ALERTS__
  __SLOTS__
  <main>
    __DIGEST__
    __AI_ANALYSIS__
    <section class="updates-section" id="updates" aria-labelledby="updates-title"__UPDATES_HIDDEN__>
      <div class="section-heading">
        <div><p class="section-kicker">本期发布后</p><h2 id="updates-title">简报后更新</h2></div>
        <p class="updates-intro">__UPDATE_COUNT__ 条新增或实质变化</p>
      </div>
      <div class="updates-list" id="updates-list"></div>
    </section>
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
  <footer class="site-footer"><span>热点新闻分析 · 个人工作台</span><span>更新于 __GENERATED_AT__ · 北京时间</span></footer>
  <script id="homepage-data" type="application/json">__HOMEPAGE_DATA__</script>
  <script>
    (function () {
      'use strict';
      var dataNode = document.getElementById('homepage-data');
      var data = { updates: [], allNews: [], categories: [] };
      try { data = JSON.parse(dataNode.textContent || '{}'); } catch (_) {}
      var PAGE_SIZE = 40;
      var FILTER_KEY = 'trendradar-filters-v1';
      var shown = PAGE_SIZE;
      var search = document.getElementById('news-search');
      var category = document.getElementById('news-category');
      var source = document.getElementById('news-source');
      var sort = document.getElementById('news-sort');
      var list = document.getElementById('all-news-list');
      var count = document.getElementById('results-count');
      var loadMore = document.getElementById('load-more');
      var empty = document.getElementById('all-news-empty');

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
      function articleRow(item, index) {
        var article = document.createElement('article');
        article.className = 'news-row';
        var number = document.createElement('span');
        number.className = 'article-number';
        number.setAttribute('aria-hidden', 'true');
        number.textContent = String(index + 1).padStart(2, '0');
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
        headingWrap.appendChild(heading);
        var label = statusLabel(item.status || '');
        if (label) {
          var badge = document.createElement('span');
          badge.className = 'status-badge status-' + (label === '突发' ? 'breaking' : 'updated');
          badge.textContent = label;
          headingWrap.appendChild(badge);
        }
        copy.appendChild(headingWrap);
        if (item.summary) {
          var summary = document.createElement('p');
          summary.className = 'article-summary';
          summary.textContent = item.summary;
          copy.appendChild(summary);
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
        data.updates.slice(0, 40).forEach(function (item, index) { fragment.appendChild(articleRow(item, index)); });
        target.replaceChildren(fragment);
      }
      function filteredNews() {
        var query = search.value.trim().toLocaleLowerCase('zh-CN');
        var selectedCategory = category.value;
        var selectedSource = source.value;
        var items = data.allNews.filter(function (item) {
          var haystack = [item.title, item.summary, item.source_name].join(' ').toLocaleLowerCase('zh-CN');
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
        visible.forEach(function (item, index) { fragment.appendChild(articleRow(item, index)); });
        list.replaceChildren(fragment);
        count.textContent = '显示 ' + visible.length + ' / ' + items.length + ' 篇';
        empty.hidden = items.length !== 0;
        loadMore.hidden = visible.length >= items.length;
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
      loadMore.addEventListener('click', function () { shown += PAGE_SIZE; renderAll(); });
      document.getElementById('reset-filters').addEventListener('click', function () {
        search.value = '';
        category.value = 'all';
        source.value = 'all';
        sort.value = 'newest';
        shown = PAGE_SIZE;
        renderAll();
      });
      document.getElementById('search-jump').addEventListener('click', function () {
        document.getElementById('all-news').scrollIntoView();
        search.focus();
      });
      document.querySelectorAll('.digest-filter').forEach(function (button) {
        button.addEventListener('click', function () {
          var selected = button.dataset.category;
          var visible = 0;
          document.querySelectorAll('.digest-filter').forEach(function (item) {
            item.setAttribute('aria-pressed', String(item === button));
          });
          document.querySelectorAll('.digest-row').forEach(function (row) {
            row.hidden = selected !== 'all' && row.dataset.category !== selected;
            if (!row.hidden) visible += 1;
          });
          var digestEmpty = document.getElementById('digest-filter-empty');
          if (digestEmpty) digestEmpty.hidden = visible !== 0;
        });
      });
      var theme = document.getElementById('theme-toggle');
      function syncTheme() {
        var dark = document.documentElement.dataset.theme === 'dark';
        theme.setAttribute('aria-pressed', String(dark));
        theme.textContent = dark ? '亮色' : '暗色';
      }
      theme.addEventListener('click', function () {
        var dark = document.documentElement.dataset.theme === 'dark';
        document.documentElement.dataset.theme = dark ? 'light' : 'dark';
        try { localStorage.setItem('trendradar-theme', dark ? 'light' : 'dark'); } catch (_) {}
        syncTheme();
      });
      renderUpdates();
      renderAll();
      syncTheme();
    })();
  </script>
</body>
</html>
'''
