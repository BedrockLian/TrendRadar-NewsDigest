# coding=utf-8
"""Render the self-contained public news workspace."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from trendradar.digest import HomepageSnapshot
from trendradar.report.helpers import html_escape
from trendradar.report.workspace_template import DOCUMENT as _DOCUMENT
from trendradar.report.workspace_theme import (
    HEAD_ASSETS,
    SHELL_BEHAVIOR_SCRIPT,
    SHELL_CSS,
    THEME_BOOTSTRAP_SCRIPT,
    THEME_CSS,
    render_sidebar,
)
from trendradar.utils.url import safe_http_url


_DEFAULT_SLOTS = [
    {"key": "morning_digest", "name": "早间新闻简报", "start": "08:00"},
    {"key": "noon_digest", "name": "午间新闻简报", "start": "12:30"},
    {"key": "evening_digest", "name": "晚间新闻简报", "start": "20:00"},
]

# Article summaries are the heaviest field in the homepage payload (~25% of
# it) and are not needed to paint the first screen.  They ship as a sibling
# JSON file that the browser pulls in right after first paint.
SUMMARIES_FILENAME = "briefings-summaries.json"


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


def _briefing_html_url(url: str) -> str:
    value = _safe_archive_url(url)
    if value.startswith("briefings/") and value.casefold().endswith(".md"):
        return value[:-3] + ".html"
    return ""


def _public_item(item: Dict[str, Any]) -> Dict[str, str]:
    """Keep only fields needed by the browser renderer.

    Two fields are deliberately reshaped for weight:

    * ``summary`` moves to :func:`build_summaries_payload`, addressed by this
      item's position in the payload;
    * ``source_name`` / ``category_name`` become indices into the payload's
      lookup arrays, stamped on by :func:`_prepare_payload`.
    """
    return {
        "title": str(item.get("title") or ""),
        "url": safe_http_url(str(item.get("url") or "")),
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
                "source_name": str(item.get("source_name") or "RSS"),
                "published_at": str(item.get("time_display") or ""),
                "category_id": "other",
                "category_name": category,
                "status": "new" if item.get("is_new") else "",
                "summary": str(item.get("summary") or ""),
            })
    return items


def _raw_items(
    homepage_snapshot: Optional[HomepageSnapshot],
    rss_items: Optional[List[Dict]],
) -> List[Dict[str, Any]]:
    """The single ordered source of truth for both payload and summaries."""

    if homepage_snapshot:
        return list(homepage_snapshot.all_news)
    return _legacy_items(rss_items)


def _prepare_payload(
    homepage_snapshot: Optional[HomepageSnapshot],
    rss_items: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Build the slim payload plus the data the sidecar needs to match it.

    Ordering is decided exactly once, here, so the positional summary array can
    never drift away from ``allNews``.
    """

    raw = _raw_items(homepage_snapshot, rss_items)
    items = [_public_item(item) for item in raw]

    sources: List[str] = []
    source_index: Dict[str, int] = {}
    categories: List[str] = []
    category_index: Dict[str, int] = {}

    for item in items:
        name = item["source_name"]
        if name not in source_index:
            source_index[name] = len(sources)
            sources.append(name)
        item["_si"] = source_index[name]

        name = item["category_name"]
        # The categories array doubles as the dropdown options, so keep the
        # digest's section order first and append anything else after it.
        if name not in category_index:
            category_index[name] = len(categories)
            categories.append(name)
        item["_ci"] = category_index[name]

        # The names now live once in the lookup arrays above; per-item copies
        # were ~32 KB of the payload.  The client resolves them back from _si
        # and _ci during hydration.
        del item["source_name"]
        del item["category_name"]

    return {
        "items": items,
        "summaries": [str(item.get("summary") or "") for item in raw],
        "sources": sources,
        "categories": categories,
    }


def build_summaries_payload(
    homepage_snapshot: Optional[HomepageSnapshot],
    rss_items: Optional[List[Dict]] = None,
) -> List[str]:
    """Return the summary for every entry of ``payload["allNews"]``, in order.

    The empty string stands for "no summary", which keeps the array dense and
    positional.
    """

    return _prepare_payload(homepage_snapshot, rss_items)["summaries"]


def write_summaries_sidecar(
    output_root: Union[Path, str],
    homepage_snapshot: Optional[HomepageSnapshot],
    rss_items: Optional[List[Dict]] = None,
) -> str:
    """Write ``output/briefings-summaries.json`` and return its path.

    The sidecar carries exactly the summaries the homepage payload omits, in the
    same order, so a browser can render the page first and enrich it after.
    """

    target = Path(output_root) / SUMMARIES_FILENAME
    payload = build_summaries_payload(homepage_snapshot, rss_items)
    target.write_text(_safe_json_data(payload), encoding="utf-8")
    return str(target)


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
    reading_url = _briefing_html_url(archive_url)
    download = (
        f'<a id="digest-download" class="download-link" href="{html_escape(archive_url)}" download>下载 Markdown <span aria-hidden="true">↓</span></a>'
        if archive_url else ""
    )
    title = html_escape(digest.period_name or "新闻简报")
    title_html = f'<a href="{html_escape(reading_url)}">{title}</a>' if reading_url else title
    filters = [f'<button class="digest-filter" type="button" data-category="all" aria-pressed="true">全部 <span>{digest.article_count}</span></button>']
    rows = []
    index = 0
    for section in digest.sections:
        category = str(section.get("name") or "其他重要新闻")
        count = int(section.get("count") or 0)
        # A section with nothing in it is not a useful filter; showing "科技与 AI 0"
        # just adds noise to the chip row.
        if count > 0:
            filters.append(
                f'<button class="digest-filter" type="button" data-category="{html_escape(category)}" aria-pressed="false">'
                f'{html_escape(category)} <span>{count}</span></button>'
            )
        for item in section.get("articles", []):
            index += 1
            status = str(item.get("status") or "")
            status_label = "突发" if status in {"breaking", "突发"} else "更新" if status in {"updated", "更新"} else ""
            badge = f'<span class="status-badge status-{html_escape(status)}">{status_label}</span>' if status_label else ""
            summary = f'<p class="article-summary">{html_escape(str(item.get("summary") or ""))}</p>' if item.get("summary") else ""
            published = str(item.get("published_at") or "")
            time_html = f'<time datetime="{html_escape(published)}">{html_escape(_display_time(published))}</time>' if published else ""
            rows.append(
                f'<article class="digest-row" data-category="{html_escape(category)}"><span class="article-number" aria-hidden="true">{index:02d}</span>'
                f'<span class="digest-state">{badge}</span>'
                f'<div class="article-copy"><div class="article-heading"><h2>{_external_link(item.get("url", ""), item.get("title", ""))}</h2></div>{summary}</div>'
                f'<div class="digest-meta"><span class="digest-source">{html_escape(str(item.get("source_name") or "RSS"))}</span>'
                f'<span class="digest-time">{time_html}</span>'
                f'<span class="digest-category">{html_escape(category)}</span></div></article>'
            )
    created_date = _display_time(digest.created_at, "%Y-%m-%d")
    created_time = _display_time(digest.created_at, "%H:%M")
    return f'''<section class="digest-section" id="digest" aria-labelledby="digest-title">
  <div class="edition-heading"><div><p class="section-kicker">{html_escape(created_date)} · 最新一期</p><h1 id="digest-title">{title_html}</h1></div>
  <div class="edition-actions"><p class="edition-ledger">{digest.article_count} 篇 · {digest.source_count} 个来源 · {html_escape(created_time)} 发布</p>{download}</div></div>
  <div class="digest-filters" aria-label="筛选本期分类">{"".join(filters)}</div>
  <div class="digest-table-head" aria-hidden="true"><span>#</span><span>状态</span><span>标题与摘要</span><span>来源</span><span>时间</span><span>分类</span></div>
  <div class="digest-list">{"".join(rows)}</div>
  <p class="filter-empty" id="digest-filter-empty" hidden>本期该分类没有新闻。</p>
</section>'''


def _render_sidebar_categories(snapshot: Optional[HomepageSnapshot]) -> str:
    digest = snapshot.latest_digest if snapshot else None
    if not digest:
        return '<span class="sidebar-empty">等待首期简报</span>'

    buttons = [
        f'<button class="sidebar-category digest-filter" type="button" data-category="all" aria-pressed="true">'
        f'<span>全部</span><strong>{digest.article_count}</strong></button>'
    ]
    for section in digest.sections:
        category = str(section.get("name") or "其他重要新闻")
        count = int(section.get("count") or 0)
        if count == 0:
            continue
        buttons.append(
            f'<button class="sidebar-category digest-filter" type="button" data-category="{html_escape(category)}" '
            f'aria-pressed="false">'
            f'<span>{html_escape(category)}</span><strong>{count}</strong></button>'
        )
    return "".join(buttons)


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
    prepared = _prepare_payload(homepage_snapshot, rss_items)
    current_items = prepared["items"]

    # "updates since the briefing" is always a subset of allNews, so ship the
    # positions instead of a second copy of every article object.
    update_indices: List[int] = []
    if homepage_snapshot:
        position = {item["url"]: index for index, item in enumerate(current_items) if item["url"]}
        seen: set = set()
        for item in homepage_snapshot.updates_since_digest:
            index = position.get(safe_http_url(str(item.get("url") or "")))
            if index is not None and index not in seen:
                seen.add(index)
                update_indices.append(index)

    # The categories array is the dropdown's option list, so the digest's own
    # section order comes first and any remaining categories follow.
    categories: List[str] = []
    if homepage_snapshot and homepage_snapshot.latest_digest:
        categories.extend(str(section.get("name") or "其他重要新闻") for section in homepage_snapshot.latest_digest.sections)
    categories.extend(name for name in prepared["categories"] if name not in categories)
    payload = _safe_json_data({
        "updates": update_indices,
        "allNews": current_items,
        "categories": categories,
        "sources": prepared["sources"],
    })
    summaries = _safe_json_data(prepared["summaries"])
    generated = _display_time(homepage_snapshot.generated_at if homepage_snapshot else now.isoformat(), "%Y-%m-%d %H:%M")
    slots_html = _render_slots(homepage_snapshot)
    sidebar_categories = _render_sidebar_categories(homepage_snapshot)
    generated_date = generated.split(" ", 1)[0]
    sidebar_extra = f'''      <section class="sidebar-section">
        <h2>今日简报</h2>
        <p class="sidebar-date">{html_escape(generated_date)}</p>
        <div class="sidebar-editions">{slots_html}</div>
      </section>
      <section class="sidebar-section">
        <h2>新闻分类</h2>
        <div class="sidebar-categories">{sidebar_categories}</div>
      </section>'''
    replacements = {
        "__WORKSPACE_HEAD__": HEAD_ASSETS + "\n" + THEME_BOOTSTRAP_SCRIPT,
        "__WORKSPACE_THEME_CSS__": THEME_CSS,
        "__WORKSPACE_SHELL_CSS__": SHELL_CSS,
        "__WORKSPACE_SHELL_SCRIPT__": SHELL_BEHAVIOR_SCRIPT,
        "__WORKSPACE_SIDEBAR__": render_sidebar(
            root_href="",
            active="digest",
            update_count=len(update_indices),
            total_count=len(current_items),
            extra_html=sidebar_extra,
            hide_empty_updates=True,
        ),
        "__ALERTS__": _render_alerts(homepage_snapshot),
        "__SLOTS__": slots_html,
        "__DIGEST__": _render_digest(homepage_snapshot, len(current_items)),
        "__AI_ANALYSIS__": _render_ai_analysis(ai_analysis),
        "__UPDATES_HIDDEN__": "" if update_indices else " hidden",
        "__UPDATE_COUNT__": str(len(update_indices)),
        "__TOTAL_COUNT__": str(len(current_items)),
        "__SOURCE_COUNT__": str(len(prepared["sources"])),
        "__CATEGORY_OPTIONS__": "".join(f'<option value="{html_escape(category)}">{html_escape(category)}</option>' for category in categories),
        "__HOMEPAGE_DATA__": payload,
        "__SUMMARIES_FILENAME__": html_escape(SUMMARIES_FILENAME),
        "__SUMMARIES_DATA__": summaries,
        "__GENERATED_AT__": html_escape(generated),
        "__GENERATED_DATE__": html_escape(generated_date),
    }
    document = _DOCUMENT
    for marker, value in replacements.items():
        document = document.replace(marker, value)
    return document
