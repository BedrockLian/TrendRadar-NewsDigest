"""Build the public, dependency-free Markdown briefing archive index."""

from __future__ import annotations

import html
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import quote


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


def _render_entry(entry: ArchiveEntry) -> str:
    href = html.escape(quote(entry.relative_path, safe="/"), quote=True)
    title = html.escape(entry.title)
    period = html.escape(entry.period_name)
    generated_time = html.escape(entry.generated_time)
    kind_label = _TYPE_LABELS[entry.kind]
    return f"""          <article class="issue" data-archive-kind="{entry.kind}">
            <div class="issue-mark" aria-hidden="true">{generated_time}</div>
            <div class="issue-body">
              <div class="issue-kicker"><span>{kind_label}</span><span>{period}</span></div>
              <h3><a href="{href}">{title}</a></h3>
              <p class="issue-meta"><span>生成于 {generated_time}</span><span>{entry.count_label}</span><a class="markdown-link" href="{href}">阅读 Markdown<span aria-hidden="true"> ↗</span></a></p>
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
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>简报存档 · TrendRadar</title>
  <style>
    :root {{
      color-scheme: light;
      --paper: #f4f2ec;
      --sheet: #fffefa;
      --ink: #182128;
      --muted: #667074;
      --rule: #d6d2c8;
      --signal: #c43d32;
      --category: #2f6c70;
      --focus: #0d7480;
      font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
    }}
    html[data-theme="dark"] {{
      color-scheme: dark;
      --paper: #171b1d;
      --sheet: #202629;
      --ink: #ecede9;
      --muted: #aeb6b6;
      --rule: #394245;
      --signal: #e46d61;
      --category: #70aeb0;
      --focus: #86c9cc;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; background: var(--paper); }}
    body {{ margin: 0; color: var(--ink); background: var(--paper); line-height: 1.55; }}
    a {{ color: inherit; text-decoration-thickness: 1px; text-underline-offset: .2em; }}
    button, a {{ -webkit-tap-highlight-color: transparent; }}
    :focus-visible {{ outline: 3px solid var(--focus); outline-offset: 4px; border-radius: 2px; }}
    .masthead {{ border-bottom: 1px solid var(--rule); background: color-mix(in srgb, var(--paper) 92%, transparent); }}
    .masthead-inner {{ max-width: 1040px; margin: 0 auto; padding: 18px 28px 16px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }}
    .brand {{ font-family: SimSun, "Songti SC", "STSong", serif; font-size: clamp(1.35rem, 3vw, 1.75rem); font-weight: 700; letter-spacing: -.025em; text-decoration: none; }}
    .header-actions {{ display: flex; align-items: center; gap: 10px; }}
    .home-link, .theme-toggle {{ border: 1px solid var(--rule); background: transparent; color: var(--ink); font: inherit; font-size: .84rem; padding: 7px 11px; cursor: pointer; text-decoration: none; }}
    .theme-toggle {{ min-width: 68px; }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 48px 28px 80px; }}
    .archive-head {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 32px; padding-bottom: 28px; border-bottom: 3px double var(--ink); }}
    .archive-head h1 {{ margin: 0; font: 700 clamp(2.4rem, 8vw, 5.4rem)/.95 SimSun, "Songti SC", "STSong", serif; letter-spacing: -.065em; }}
    .archive-head p {{ max-width: 27rem; margin: 14px 0 0; color: var(--muted); }}
    .edition-stamp {{ font-family: Consolas, "SFMono-Regular", monospace; text-align: right; color: var(--muted); font-size: .76rem; letter-spacing: .04em; white-space: nowrap; }}
    .edition-stamp strong {{ display: block; margin-bottom: 5px; color: var(--signal); font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; }}
    .filters {{ position: sticky; top: 0; z-index: 3; display: flex; align-items: center; gap: 4px; margin: 0 -8px 34px; padding: 12px 8px; overflow-x: auto; background: color-mix(in srgb, var(--paper) 94%, transparent); border-bottom: 1px solid var(--rule); backdrop-filter: blur(10px); scrollbar-width: thin; }}
    .filter {{ flex: none; border: 0; border-bottom: 2px solid transparent; padding: 8px 12px 7px; background: transparent; color: var(--muted); font: 600 .86rem/1 "PingFang SC", "Microsoft YaHei", sans-serif; cursor: pointer; }}
    .filter[aria-pressed="true"] {{ color: var(--ink); border-color: var(--signal); }}
    .filter-count {{ margin-left: 5px; color: var(--category); font-family: Consolas, "SFMono-Regular", monospace; font-size: .76rem; }}
    .date-group {{ display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 34px; border-top: 1px solid var(--rule); }}
    .date-group:first-of-type {{ border-top: 0; }}
    .date-group h2 {{ position: sticky; top: 76px; align-self: start; margin: 0; padding: 24px 0; color: var(--muted); font: 600 .78rem/1.5 Consolas, "SFMono-Regular", monospace; }}
    .issue-list {{ min-width: 0; }}
    .issue {{ display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 22px; padding: 25px 0 27px; border-bottom: 1px solid var(--rule); }}
    .issue-mark {{ padding-top: 4px; color: var(--signal); font: 700 .78rem/1.2 Consolas, "SFMono-Regular", monospace; }}
    .issue-kicker {{ display: flex; gap: 12px; color: var(--category); font-size: .75rem; font-weight: 700; letter-spacing: .08em; }}
    .issue-kicker span + span {{ color: var(--muted); font-weight: 500; letter-spacing: 0; }}
    .issue h3 {{ max-width: 42rem; margin: 6px 0 10px; font: 700 clamp(1.24rem, 2.5vw, 1.65rem)/1.28 SimSun, "Songti SC", "STSong", serif; overflow-wrap: anywhere; }}
    .issue h3 a {{ text-decoration: none; }}
    .issue h3 a:hover {{ text-decoration: underline; text-decoration-color: var(--signal); }}
    .issue-meta {{ display: flex; flex-wrap: wrap; gap: 7px 18px; margin: 0; color: var(--muted); font: .78rem/1.5 Consolas, "SFMono-Regular", monospace; }}
    .markdown-link {{ color: var(--ink); font-family: "PingFang SC", "Microsoft YaHei", sans-serif; font-weight: 600; }}
    .empty {{ margin: 48px 0; padding: 32px 0; border-block: 1px solid var(--rule); color: var(--muted); }}
    .no-results {{ display: none; margin: 40px 0; color: var(--muted); }}
    footer {{ max-width: 1040px; margin: 0 auto; padding: 24px 28px 40px; border-top: 1px solid var(--rule); color: var(--muted); font: .75rem/1.5 Consolas, "SFMono-Regular", monospace; }}
    [hidden] {{ display: none !important; }}
    @media (max-width: 720px) {{
      .masthead-inner {{ padding: 13px 18px; gap: 12px; }}
      .home-link {{ display: none; }}
      main {{ padding: 34px 18px 60px; }}
      .archive-head {{ grid-template-columns: 1fr; gap: 18px; padding-bottom: 23px; }}
      .archive-head h1 {{ font-size: clamp(2.65rem, 17vw, 4rem); }}
      .edition-stamp {{ text-align: left; }}
      .filters {{ margin: 0 -18px 24px; padding-inline: 18px; }}
      .date-group {{ display: block; }}
      .date-group h2 {{ position: static; padding: 22px 0 10px; }}
      .issue {{ grid-template-columns: 50px minmax(0, 1fr); gap: 10px; padding: 18px 0 20px; }}
      .issue h3 {{ font-size: 1.22rem; }}
      .issue-meta {{ gap: 5px 13px; }}
      footer {{ padding-inline: 18px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}
    @media print {{
      .header-actions, .filters, footer {{ display: none; }}
      main {{ max-width: none; padding: 0; }}
      .date-group h2 {{ position: static; }}
    }}
  </style>
  <script>
    (function () {{
      try {{
        var saved = localStorage.getItem('trendradar-theme');
        if (saved === 'dark' || (!saved && matchMedia('(prefers-color-scheme: dark)').matches)) {{
          document.documentElement.dataset.theme = 'dark';
        }}
      }} catch (_) {{}}
    }})();
  </script>
</head>
<body>
  <header class="masthead">
    <div class="masthead-inner">
      <a class="brand" href="../">TrendRadar</a>
      <div class="header-actions">
        <a class="home-link" href="../">返回最新一期</a>
        <button class="theme-toggle" id="theme-toggle" type="button" aria-label="切换深浅主题">暗色</button>
      </div>
    </div>
  </header>
  <main>
    <div class="archive-head">
      <div>
        <h1>简报存档</h1>
        <p>按日期查阅时段简报、每周趋势与突发更新。每条记录直接打开原始 Markdown。</p>
      </div>
      <div class="edition-stamp"><strong>存档更新</strong>{html.escape(updated)}</div>
    </div>
    <nav class="filters" aria-label="筛选简报类型">
      <button class="filter" type="button" data-filter="all" aria-pressed="true">全部<span class="filter-count">{len(entries)}</span></button>
      <button class="filter" type="button" data-filter="digest" aria-pressed="false">时段简报<span class="filter-count">{counts['digest']}</span></button>
      <button class="filter" type="button" data-filter="weekly" aria-pressed="false">周报<span class="filter-count">{counts['weekly']}</span></button>
      <button class="filter" type="button" data-filter="alert" aria-pressed="false">突发<span class="filter-count">{counts['alert']}</span></button>
    </nav>
    <div id="archive-list">
{listing}
    </div>
    <p class="no-results" id="no-results" role="status">此分类暂时没有记录。</p>
  </main>
  <footer>TrendRadar · 北京时间 · Markdown 简报保留 30 天</footer>
  <script>
    (function () {{
      var root = document.documentElement;
      var themeButton = document.getElementById('theme-toggle');
      var filters = Array.from(document.querySelectorAll('[data-filter]'));
      var issues = Array.from(document.querySelectorAll('[data-archive-kind]'));
      var groups = Array.from(document.querySelectorAll('[data-date-group]'));
      var noResults = document.getElementById('no-results');

      function syncThemeLabel() {{
        themeButton.textContent = root.dataset.theme === 'dark' ? '浅色' : '暗色';
      }}
      syncThemeLabel();
      themeButton.addEventListener('click', function () {{
        if (root.dataset.theme === 'dark') {{ root.removeAttribute('data-theme'); }}
        else {{ root.dataset.theme = 'dark'; }}
        try {{ localStorage.setItem('trendradar-theme', root.dataset.theme || 'light'); }} catch (_) {{}}
        syncThemeLabel();
      }});

      function applyFilter(kind) {{
        var visible = 0;
        filters.forEach(function (button) {{ button.setAttribute('aria-pressed', String(button.dataset.filter === kind)); }});
        issues.forEach(function (issue) {{
          var show = kind === 'all' || issue.dataset.archiveKind === kind;
          issue.hidden = !show;
          if (show) visible += 1;
        }});
        groups.forEach(function (group) {{
          group.hidden = !group.querySelector('[data-archive-kind]:not([hidden])');
        }});
        noResults.style.display = issues.length && visible === 0 ? 'block' : 'none';
        try {{ localStorage.setItem('trendradar-archive-filter', kind); }} catch (_) {{}}
      }}
      filters.forEach(function (button) {{ button.addEventListener('click', function () {{ applyFilter(button.dataset.filter); }}); }});
      var savedFilter = 'all';
      try {{ savedFilter = localStorage.getItem('trendradar-archive-filter') || 'all'; }} catch (_) {{}}
      if (!filters.some(function (button) {{ return button.dataset.filter === savedFilter; }})) savedFilter = 'all';
      applyFilter(savedFilter);
    }})();
  </script>
</body>
</html>
"""


def build_index(root: Path, generated_at: datetime | None = None) -> Path:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = root / "index.html"
    output.write_text(render_index(collect_entries(root), generated_at), encoding="utf-8")
    return output


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：build_briefing_index.py <简报目录>")
    build_index(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
