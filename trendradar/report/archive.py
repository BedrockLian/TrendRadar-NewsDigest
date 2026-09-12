"""Build the public briefing archive index and safe HTML reading pages."""

from __future__ import annotations

import html
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import quote

from trendradar.report.workspace_theme import (
    HEAD_ASSETS,
    SHELL_BEHAVIOR_SCRIPT,
    SHELL_CSS,
    THEME_BOOTSTRAP_SCRIPT,
    THEME_CSS,
    render_sidebar,
    render_topbar,
)
from trendradar.utils.url import safe_http_url


_DIGEST_FILE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<time>\d{4})-(?P<period>.+)\.md$"
)
_WEEKLY_FILE = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{2})\.md$")
_ALERT_FILE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\.md$")
_GENERATED_AT = re.compile(
    r"生成时间[：:]\s*(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{1,2}:\d{2})"
)
_ARTICLE_COUNT = re.compile(r"共\s*(?P<count>\d+)\s*篇")
_HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_ALERT_TIME = re.compile(r"^##\s+(?P<time>\d{1,2}:\d{2})\s+突发提醒\s*$", re.MULTILINE)
_LINK_ITEM = re.compile(
    r"^(?P<indent>\s*)(?P<marker>\d+\.|-)\s+\[(?P<title>.+?)\]\((?P<url>\S+?)\)(?P<tail>.*)$"
)
_INLINE_TOKEN = re.compile(r"\[([^\]]+)\]\(([^\s)]+)\)|\*\*([^*]+)\*\*")
_STATUS = re.compile(r"\*\*\[([^\]]+)\]\*\*")
_FULLWIDTH_SOURCE = re.compile(r"^（(.+?)）$")

_PERIOD_NAMES = {
    "morning_digest": "早间新闻简报",
    "noon_digest": "午间新闻简报",
    "evening_digest": "晚间新闻简报",
}
_TYPE_LABELS = {"digest": "时段简报", "weekly": "周报", "alert": "突发"}
_WEEKDAYS = "一二三四五六日"


@dataclass(frozen=True)
class ArchiveEntry:
    relative_path: str
    kind: str
    title: str
    publication_date: date
    generated_time: str
    article_count: int
    period_name: str

    @property
    def count_label(self) -> str:
        unit = "条" if self.kind == "alert" else "篇"
        return f"{self.article_count} {unit}"

    @property
    def detail_path(self) -> str:
        return str(PurePosixPath(self.relative_path).with_suffix(".html"))


def _read_markdown(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _heading(content: str, fallback: str) -> str:
    match = _HEADING.search(content)
    return match.group(1).strip() if match else fallback


def _count_articles(content: str, kind: str) -> int:
    explicit = _ARTICLE_COUNT.search(content)
    if explicit:
        return int(explicit.group("count"))
    if kind == "digest":
        return len(re.findall(r"^\d+\.\s+\[.+?\]\(.+?\)", content, re.MULTILINE))
    return len(re.findall(r"^-\s+\[.+?\]\(.+?\)", content, re.MULTILINE))


def _file_time(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).astimezone().strftime("%H:%M")
    except OSError:
        return "--:--"


def _parse_entry(root: Path, path: Path) -> ArchiveEntry | None:
    relative = path.relative_to(root).as_posix()
    content = _read_markdown(path)
    parents = {part.casefold() for part in path.relative_to(root).parts[:-1]}

    if "weekly" in parents:
        match = _WEEKLY_FILE.match(path.name)
        if not match:
            return None
        year, week = int(match.group("year")), int(match.group("week"))
        try:
            publication_date = date.fromisocalendar(year, week, 7)
        except ValueError:
            return None
        fallback = f"{year}-W{week:02d} 新闻趋势周报"
        return ArchiveEntry(
            relative_path=relative,
            kind="weekly",
            title=_heading(content, fallback),
            publication_date=publication_date,
            # Weekly reports are emitted with the Sunday evening digest.
            generated_time="20:00",
            article_count=_count_articles(content, "weekly"),
            period_name=f"第 {week:02d} 周",
        )

    if "alerts" in parents:
        match = _ALERT_FILE.match(path.name)
        if not match:
            return None
        try:
            publication_date = date.fromisoformat(match.group("date"))
        except ValueError:
            return None
        alert_times = _ALERT_TIME.findall(content)
        return ArchiveEntry(
            relative_path=relative,
            kind="alert",
            title=_heading(content, f"{publication_date.isoformat()} 突发与重要更新"),
            publication_date=publication_date,
            generated_time=alert_times[-1] if alert_times else _file_time(path),
            article_count=_count_articles(content, "alert"),
            period_name="突发与重要更新",
        )

    match = _DIGEST_FILE.match(path.name)
    if not match:
        return None
    try:
        publication_date = date.fromisoformat(match.group("date"))
    except ValueError:
        return None
    period_key = match.group("period")
    period_name = _PERIOD_NAMES.get(period_key, period_key.replace("_", " "))
    generated = _GENERATED_AT.search(content)
    file_clock = match.group("time")
    generated_time = (
        generated.group("time").zfill(5)
        if generated
        else f"{file_clock[:2]}:{file_clock[2:]}"
    )
    return ArchiveEntry(
        relative_path=relative,
        kind="digest",
        title=_heading(content, f"{publication_date.isoformat()} {period_name}"),
        publication_date=publication_date,
        generated_time=generated_time,
        article_count=_count_articles(content, "digest"),
        period_name=period_name,
    )


def collect_entries(root: Path) -> list[ArchiveEntry]:
    entries = (
        entry
        for path in root.rglob("*.md")
        if (entry := _parse_entry(root, path)) is not None
    )
    return sorted(
        entries,
        key=lambda entry: (
            entry.publication_date,
            entry.generated_time,
            entry.relative_path,
        ),
        reverse=True,
    )


def _date_label(value: date) -> str:
    return f"{value.year}年{value.month}月{value.day}日 · 周{_WEEKDAYS[value.weekday()]}"


def _render_inline(value: str) -> str:
    """Render the tiny inline subset emitted by the briefing generator."""

    output: list[str] = []
    cursor = 0
    for match in _INLINE_TOKEN.finditer(value):
        output.append(html.escape(value[cursor:match.start()]))
        if match.group(1) is not None:
            label = html.escape(match.group(1))
            safe_url = safe_http_url(match.group(2))
            if safe_url:
                output.append(
                    f'<a href="{html.escape(safe_url, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>'
                )
            else:
                output.append(label)
        else:
            output.append(f"<strong>{html.escape(match.group(3) or '')}</strong>")
        cursor = match.end()
    output.append(html.escape(value[cursor:]))
    return "".join(output)


def _parse_markdown_blocks(content: str) -> list[dict[str, object]]:
    """Parse only the controlled Markdown shapes TrendRadar itself writes."""

    blocks: list[dict[str, object]] = []
    current_article: dict[str, object] | None = None
    article_number = 0
    skipped_title = False

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            current_article = None
            continue
        if not skipped_title and stripped.startswith("# "):
            skipped_title = True
            continue

        if current_article is not None and raw_line[:1].isspace() and stripped.startswith("- "):
            detail = stripped[2:].strip()
            if detail.startswith("来源："):
                current_article["source"] = detail.removeprefix("来源：").strip()
            elif detail.startswith("简介："):
                current_article["summary"] = detail.removeprefix("简介：").strip()
            elif not current_article.get("summary"):
                current_article["summary"] = detail
            continue

        link_match = _LINK_ITEM.match(raw_line)
        if link_match:
            article_number += 1
            tail = link_match.group("tail").strip()
            status_match = _STATUS.search(tail)
            source_match = _FULLWIDTH_SOURCE.match(tail)
            current_article = {
                "kind": "article",
                "number": article_number,
                "title": link_match.group("title"),
                "url": safe_http_url(link_match.group("url")),
                "status": status_match.group(1).strip() if status_match else "",
                "source": source_match.group(1).strip() if source_match else "",
                "summary": "",
            }
            blocks.append(current_article)
            continue

        current_article = None
        if stripped.startswith("### "):
            blocks.append({"kind": "heading", "level": 3, "text": stripped[4:].strip()})
        elif stripped.startswith("## "):
            blocks.append({"kind": "heading", "level": 2, "text": stripped[3:].strip()})
        elif stripped.startswith("> "):
            blocks.append({"kind": "quote", "text": stripped[2:].strip()})
        elif stripped.startswith("- "):
            blocks.append({"kind": "note", "text": stripped[2:].strip()})
        else:
            blocks.append({"kind": "paragraph", "text": stripped})
    return blocks


def _render_detail_body(content: str) -> str:
    rendered: list[str] = []
    for block in _parse_markdown_blocks(content):
        kind = str(block["kind"])
        if kind == "heading":
            level = 3 if block.get("level") == 3 else 2
            rendered.append(f'<h{level} class="brief-heading">{_render_inline(str(block["text"]))}</h{level}>')
        elif kind == "quote":
            rendered.append(f'<p class="brief-lede">{_render_inline(str(block["text"]))}</p>')
        elif kind == "note":
            rendered.append(f'<p class="brief-note"><span aria-hidden="true">—</span>{_render_inline(str(block["text"]))}</p>')
        elif kind == "paragraph":
            rendered.append(f'<p class="brief-paragraph">{_render_inline(str(block["text"]))}</p>')
        elif kind == "article":
            url = str(block.get("url") or "")
            title = html.escape(str(block.get("title") or ""))
            title_html = (
                f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{title}</a>'
                if url else title
            )
            status = str(block.get("status") or "")
            status_html = ""
            if status:
                signal = status in {"突发", "更新", "breaking", "updated"}
                status_class = " detail-status-signal" if signal else ""
                status_html = f'<span class="detail-status{status_class}">{html.escape(status)}</span>'
            summary = str(block.get("summary") or "")
            summary_html = f'<p>{_render_inline(summary)}</p>' if summary else ""
            source = str(block.get("source") or "")
            source_html = f'<span class="detail-source">{html.escape(source)}</span>' if source else ""
            rendered.append(
                f'<article class="brief-article"><span class="brief-number" aria-hidden="true">{int(block["number"]):02d}</span>'
                f'<div class="brief-copy"><div class="brief-article-title">{status_html}<h3>{title_html}</h3></div>{summary_html}</div>{source_html}</article>'
            )
    return "\n".join(rendered) or '<p class="brief-empty">这份简报没有可显示的内容。</p>'


def render_detail(entry: ArchiveEntry, content: str) -> str:
    parts = PurePosixPath(entry.relative_path).parts
    home_root = "../" * len(parts)
    archive_href = "../" * max(0, len(parts) - 1) or "./"
    markdown_href = quote(PurePosixPath(entry.relative_path).name, safe="")
    kind_label = _TYPE_LABELS[entry.kind]
    signal_class = " brief-kind-signal" if entry.kind == "alert" else ""
    sidebar_extra = f'''      <section class="sidebar-section brief-sidebar-meta">
        <h2>本期信息</h2>
        <p>{html.escape(kind_label)}</p>
        <p>{html.escape(entry.publication_date.isoformat())}</p>
        <p>{html.escape(entry.generated_time)} · {html.escape(entry.count_label)}</p>
      </section>'''
    sidebar = render_sidebar(root_href=home_root, active="archive", extra_html=sidebar_extra)
    topbar = render_topbar("简报存档", "archive", entry.publication_date.isoformat())
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#071923">
  <title>{html.escape(entry.title)} · TrendRadar</title>
{HEAD_ASSETS}
{THEME_BOOTSTRAP_SCRIPT}
  <style>
{THEME_CSS}
{SHELL_CSS}
    .brief-sidebar-meta p {{ margin: 5px 0; color: var(--muted); font-size: .78rem; }}
    .brief-page {{ min-height: calc(100vh - 72px); background: var(--surface); }}
    .brief-inner {{ width: min(100%, 940px); margin: 0 auto; padding: 38px 34px 76px; }}
    .back-link {{ display: inline-flex; align-items: center; gap: 7px; margin-bottom: 28px; color: var(--muted); font-size: .8rem; text-decoration: none; }}
    .back-link:hover {{ color: var(--accent); }}
    .brief-header {{ padding-bottom: 28px; border-bottom: 1px solid var(--rule-strong); }}
    .brief-kind {{ display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 4px; color: var(--accent); background: var(--accent-soft); font-size: .7rem; font-weight: 680; }}
    .brief-kind-signal {{ color: var(--signal); background: var(--signal-soft); }}
    .brief-header h1 {{ max-width: 800px; margin: 12px 0 13px; color: var(--ink-strong); font-size: clamp(2rem, 5vw, 3.5rem); line-height: 1.06; letter-spacing: -.045em; overflow-wrap: anywhere; }}
    .brief-actions {{ display: flex; align-items: center; flex-wrap: wrap; gap: 10px 18px; color: var(--muted); font-size: .78rem; }}
    .brief-actions a {{ display: inline-flex; align-items: center; gap: 7px; min-height: 36px; padding: 7px 11px; border: 1px solid var(--accent); border-radius: 5px; color: var(--accent); font-weight: 650; text-decoration: none; }}
    .brief-content {{ margin-top: 32px; }}
    .brief-heading {{ margin: 36px 0 10px; color: var(--ink-strong); overflow-wrap: anywhere; }}
    h2.brief-heading {{ padding-bottom: 10px; border-bottom: 1px solid var(--rule); font-size: 1.15rem; }}
    h3.brief-heading {{ color: var(--accent); font-size: .9rem; }}
    .brief-lede {{ margin: 0 0 26px; padding: 14px 16px; border-left: 3px solid var(--accent); background: var(--surface-raised); color: var(--muted); }}
    .brief-paragraph {{ max-width: 760px; margin: 12px 0; color: var(--ink); }}
    .brief-note {{ display: flex; gap: 10px; max-width: 760px; margin: 9px 0; color: var(--muted); }}
    .brief-note > span {{ color: var(--accent); }}
    .brief-article {{ display: grid; grid-template-columns: 38px minmax(0, 1fr) 140px; gap: 14px; padding: 18px 0; border-top: 1px solid var(--rule); }}
    .brief-number {{ padding-top: 3px; color: var(--signal); font: 650 .76rem var(--font-mono); }}
    .brief-copy {{ min-width: 0; }}
    .brief-article-title {{ display: flex; align-items: flex-start; gap: 8px; }}
    .brief-article h3 {{ min-width: 0; margin: 0; color: var(--ink-strong); font-size: 1rem; line-height: 1.34; overflow-wrap: anywhere; }}
    .brief-article h3 a {{ text-decoration: none; }}
    .brief-copy p {{ display: -webkit-box; margin: 7px 0 0; overflow: hidden; color: var(--muted); font-size: .82rem; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }}
    .detail-status {{ flex: 0 0 auto; padding: 3px 7px; border-radius: 4px; color: var(--accent); background: var(--accent-soft); font-size: .68rem; font-weight: 680; }}
    .detail-status-signal {{ color: var(--signal); background: var(--signal-soft); }}
    .detail-source {{ padding-top: 3px; color: var(--muted); font-size: .72rem; text-align: right; overflow-wrap: anywhere; }}
    .brief-empty {{ padding: 44px 0; color: var(--muted); }}
    .brief-footer {{ padding: 18px 34px 28px; border-top: 1px solid var(--rule); color: var(--faint); font-size: .7rem; }}
    @media (max-width: 720px) {{
      .brief-inner {{ padding: 28px 16px 56px; }}
      .brief-header h1 {{ font-size: clamp(1.8rem, 10vw, 2.5rem); }}
      .brief-article {{ grid-template-columns: 30px minmax(0, 1fr); gap: 10px; }}
      .detail-source {{ grid-column: 2; padding-top: 0; text-align: left; }}
      .brief-article-title {{ display: grid; justify-items: start; }}
      .brief-footer {{ padding-inline: 16px; }}
    }}
    @media print {{ .sidebar, .topbar, .back-link, .brief-footer {{ display: none !important; }} .app-frame {{ display: block; }} .brief-inner {{ width: auto; padding: 0; }} body, .brief-page {{ background: #fff; color: #000; }} .brief-article {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <button class="sidebar-scrim" id="sidebar-scrim" type="button" aria-label="关闭导航"></button>
  <div class="app-frame">
{sidebar}
    <div class="app-page">
{topbar}
      <main class="brief-page">
        <div class="brief-inner">
          <a class="back-link" href="{html.escape(archive_href, quote=True)}"><i class="bi bi-arrow-left" aria-hidden="true"></i>返回简报存档</a>
          <header class="brief-header">
            <span class="brief-kind{signal_class}">{html.escape(kind_label)}</span>
            <h1>{html.escape(entry.title)}</h1>
            <div class="brief-actions"><span>{html.escape(entry.publication_date.isoformat())} · {html.escape(entry.generated_time)} · {html.escape(entry.count_label)}</span><a href="{html.escape(markdown_href, quote=True)}" download><i class="bi bi-download" aria-hidden="true"></i>下载 Markdown</a></div>
          </header>
          <div class="brief-content">{_render_detail_body(content)}</div>
        </div>
      </main>
      <footer class="brief-footer">TrendRadar · 北京时间 · Markdown 简报保留 30 天</footer>
    </div>
  </div>
{SHELL_BEHAVIOR_SCRIPT}
</body>
</html>
"""


def _render_entry(entry: ArchiveEntry) -> str:
    detail_href = html.escape(quote(entry.detail_path, safe="/"), quote=True)
    markdown_href = html.escape(quote(entry.relative_path, safe="/"), quote=True)
    title = html.escape(entry.title)
    period = html.escape(entry.period_name)
    generated_time = html.escape(entry.generated_time)
    kind_label = _TYPE_LABELS[entry.kind]
    return f"""          <article class="issue" data-archive-kind="{entry.kind}">
            <div class="issue-mark" aria-hidden="true">{generated_time}</div>
            <div class="issue-body">
              <div class="issue-kicker"><span>{kind_label}</span><span>{period}</span></div>
              <h3><a href="{detail_href}">{title}</a></h3>
              <p class="issue-meta"><span>生成于 {generated_time}</span><span>{entry.count_label}</span><a class="markdown-link" href="{markdown_href}" download>下载 Markdown<span aria-hidden="true"> ↓</span></a></p>
            </div>
          </article>"""


def _render_groups(entries: Iterable[ArchiveEntry]) -> str:
    grouped: dict[date, list[ArchiveEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.publication_date].append(entry)
    if not grouped:
        return '<p class="empty" id="archive-empty">暂无简报。首期生成后会出现在这里。</p>'
    groups = []
    for publication_date in sorted(grouped, reverse=True):
        issues = "\n".join(_render_entry(entry) for entry in grouped[publication_date])
        groups.append(
            f"""      <section class="date-group" data-date-group>
        <h2>{html.escape(_date_label(publication_date))}</h2>
        <div class="issue-list">
{issues}
        </div>
      </section>"""
        )
    return "\n".join(groups)


def render_index(entries: list[ArchiveEntry], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now().astimezone()
    updated = generated_at.strftime("%Y-%m-%d %H:%M")
    counts = Counter(entry.kind for entry in entries)
    listing = _render_groups(entries)
    filter_defs = [
        ("all", "全部", len(entries)),
        ("digest", "时段简报", counts["digest"]),
        ("weekly", "周报", counts["weekly"]),
        ("alert", "突发", counts["alert"]),
    ]
    sidebar_filters = "".join(
        f'<button class="sidebar-category archive-filter" type="button" data-archive-filter="{kind}" aria-pressed="{str(kind == "all").lower()}"><span>{label}</span><strong>{count}</strong></button>'
        for kind, label, count in filter_defs
    )
    sidebar_extra = f'''      <section class="sidebar-section">
        <h2>简报类型</h2>
        <div class="sidebar-categories">{sidebar_filters}</div>
      </section>'''
    sidebar = render_sidebar(root_href="../", active="archive", extra_html=sidebar_extra)
    topbar = render_topbar("简报存档", "archive", updated)
    filters = "".join(
        f'<button class="archive-filter" type="button" data-archive-filter="{kind}" aria-pressed="{str(kind == "all").lower()}">{label}<span>{count}</span></button>'
        for kind, label, count in filter_defs
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#071923">
  <title>简报存档 · TrendRadar</title>
{HEAD_ASSETS}
{THEME_BOOTSTRAP_SCRIPT}
  <style>
{THEME_CSS}
{SHELL_CSS}
    .sidebar-categories {{ display: grid; gap: 3px; }}
    .sidebar-category {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%; min-height: 36px; padding: 7px 10px; border: 0; border-left: 3px solid transparent; border-radius: 4px; background: transparent; color: var(--muted); text-align: left; }}
    .sidebar-category:hover {{ color: var(--ink); background: var(--surface-raised); }}
    .sidebar-category[aria-pressed="true"] {{ color: var(--ink-strong); background: var(--sidebar-active); border-left-color: var(--accent); }}
    .sidebar-category strong {{ color: var(--faint); font-size: .76rem; font-weight: 550; }}
    .archive-page {{ min-height: calc(100vh - 72px); background: var(--surface); }}
    .archive-main {{ width: min(100%, 1040px); margin: 0 auto; padding: 38px 34px 76px; }}
    .archive-head {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding-bottom: 25px; border-bottom: 1px solid var(--rule-strong); }}
    .section-kicker {{ margin: 0 0 7px; color: var(--accent); font-size: .72rem; font-weight: 700; letter-spacing: .06em; }}
    .archive-head h1 {{ margin: 0; color: var(--ink-strong); font-size: clamp(2rem, 5vw, 3.35rem); line-height: 1.05; letter-spacing: -.04em; }}
    .archive-summary {{ max-width: 560px; margin: 10px 0 0; color: var(--muted); font-size: .86rem; }}
    .archive-updated {{ flex: 0 0 auto; margin: 0; color: var(--faint); font: .72rem var(--font-mono); white-space: nowrap; }}
    .archive-filters {{ position: sticky; top: 72px; z-index: 20; display: flex; gap: 7px; margin: 0 -4px 24px; padding: 14px 4px; overflow-x: auto; background: var(--surface); border-bottom: 1px solid var(--rule); scrollbar-width: thin; }}
    .archive-filters .archive-filter {{ flex: 0 0 auto; min-height: 34px; padding: 6px 10px; border: 1px solid var(--rule-strong); border-radius: 5px; background: transparent; color: var(--muted); font-size: .76rem; white-space: nowrap; }}
    .archive-filters .archive-filter:hover {{ color: var(--ink); border-color: var(--accent); }}
    .archive-filters .archive-filter[aria-pressed="true"] {{ color: #04171d; background: var(--accent-bright); border-color: var(--accent-bright); font-weight: 670; }}
    .archive-filter span {{ margin-left: 5px; font-family: var(--font-mono); }}
    .date-group {{ display: grid; grid-template-columns: 170px minmax(0, 1fr); gap: 32px; border-top: 1px solid var(--rule); }}
    .date-group:first-of-type {{ border-top: 0; }}
    .date-group h2 {{ position: sticky; top: 142px; align-self: start; margin: 0; padding: 22px 0; color: var(--muted); font: 600 .75rem/1.5 var(--font-mono); }}
    .issue-list {{ min-width: 0; }}
    .issue {{ display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 18px; padding: 21px 0 23px; border-bottom: 1px solid var(--rule); }}
    .issue-mark {{ padding-top: 3px; color: var(--signal); font: 650 .74rem var(--font-mono); }}
    .issue-kicker {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--accent); font-size: .7rem; font-weight: 680; }}
    .issue-kicker span + span {{ color: var(--muted); font-weight: 520; }}
    .issue h3 {{ max-width: 720px; margin: 6px 0 9px; color: var(--ink-strong); font-size: 1rem; line-height: 1.36; overflow-wrap: anywhere; }}
    .issue h3 a {{ text-decoration: none; }}
    .issue-meta {{ display: flex; flex-wrap: wrap; gap: 7px 16px; margin: 0; color: var(--muted); font-size: .72rem; }}
    .markdown-link {{ color: var(--accent); font-weight: 650; text-decoration: none; }}
    .empty, .no-results {{ margin: 36px 0; padding: 34px 0; border-block: 1px solid var(--rule); color: var(--muted); }}
    .no-results {{ display: none; }}
    .archive-footer {{ padding: 18px 34px 28px; border-top: 1px solid var(--rule); color: var(--faint); font-size: .7rem; }}
    @media (max-width: 960px) {{ .archive-filters {{ top: 64px; }} }}
    @media (max-width: 720px) {{
      .archive-main {{ padding: 28px 16px 56px; }}
      .archive-head {{ align-items: flex-start; flex-direction: column; gap: 14px; }}
      .archive-updated {{ white-space: normal; }}
      .archive-filters {{ margin-inline: -16px; padding-inline: 16px; }}
      .date-group {{ display: block; }}
      .date-group h2 {{ position: static; padding: 20px 0 9px; }}
      .issue {{ grid-template-columns: 48px minmax(0, 1fr); gap: 10px; padding: 17px 0 19px; }}
      .archive-footer {{ padding-inline: 16px; }}
    }}
    @media print {{ .sidebar, .topbar, .archive-filters, .archive-footer {{ display: none !important; }} .app-frame {{ display: block; }} .archive-main {{ width: auto; padding: 0; }} body, .archive-page {{ background: #fff; color: #000; }} .date-group h2 {{ position: static; }} }}
  </style>
</head>
<body>
  <button class="sidebar-scrim" id="sidebar-scrim" type="button" aria-label="关闭导航"></button>
  <div class="app-frame">
{sidebar}
    <div class="app-page">
{topbar}
      <main class="archive-page">
        <div class="archive-main">
          <header class="archive-head">
            <div><p class="section-kicker">历史简报</p><h1>简报存档</h1><p class="archive-summary">按日期查阅时段简报、每周趋势与突发更新。</p></div>
            <p class="archive-updated">更新于 {html.escape(updated)} · 保留 30 天</p>
          </header>
          <nav class="archive-filters" aria-label="筛选简报类型">{filters}</nav>
          <div id="archive-list">{listing}</div>
          <p class="no-results" id="no-results" role="status">此分类暂时没有记录。</p>
        </div>
      </main>
      <footer class="archive-footer">TrendRadar · 北京时间 · Markdown 简报保留 30 天</footer>
    </div>
  </div>
{SHELL_BEHAVIOR_SCRIPT}
  <script>
    (function () {{
      var filters = Array.from(document.querySelectorAll('[data-archive-filter]'));
      var issues = Array.from(document.querySelectorAll('[data-archive-kind]'));
      var groups = Array.from(document.querySelectorAll('[data-date-group]'));
      var noResults = document.getElementById('no-results');
      function applyFilter(kind) {{
        var visible = 0;
        filters.forEach(function (button) {{ button.setAttribute('aria-pressed', String(button.dataset.archiveFilter === kind)); }});
        issues.forEach(function (issue) {{
          var show = kind === 'all' || issue.dataset.archiveKind === kind;
          issue.hidden = !show;
          if (show) visible += 1;
        }});
        groups.forEach(function (group) {{ group.hidden = !group.querySelector('[data-archive-kind]:not([hidden])'); }});
        noResults.style.display = issues.length && visible === 0 ? 'block' : 'none';
        try {{ localStorage.setItem('trendradar-archive-filter', kind); }} catch (_) {{}}
      }}
      filters.forEach(function (button) {{ button.addEventListener('click', function () {{ applyFilter(button.dataset.archiveFilter); }}); }});
      var saved = 'all';
      try {{ saved = localStorage.getItem('trendradar-archive-filter') || 'all'; }} catch (_) {{}}
      if (!filters.some(function (button) {{ return button.dataset.archiveFilter === saved; }})) saved = 'all';
      applyFilter(saved);
    }})();
  </script>
</body>
</html>
"""


def build_index(root: Path, generated_at: datetime | None = None) -> Path:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    entries = collect_entries(root)
    for entry in entries:
        markdown_path = root.joinpath(*PurePosixPath(entry.relative_path).parts)
        detail_path = root.joinpath(*PurePosixPath(entry.detail_path).parts)
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            render_detail(entry, _read_markdown(markdown_path)), encoding="utf-8"
        )
    output = root / "index.html"
    output.write_text(render_index(entries, generated_at), encoding="utf-8")
    return output


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python -m trendradar.report.archive <简报目录>")
    build_index(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
