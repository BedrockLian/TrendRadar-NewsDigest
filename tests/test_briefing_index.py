"""Tests for the public Markdown briefing archive index."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from deployment.build_briefing_index import build_index, collect_entries


class BriefingIndexTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_collects_all_archive_types_and_extracts_metadata(self):
        self.write(
            "2026-09/2026-09-10-0802-morning_digest.md",
            "# 2026-09-10 早间新闻简报\n\n"
            "> 生成时间：2026-09-10 08:02｜共 2 篇\n\n"
            "1. [新闻 A](https://example.com/a)\n2. [新闻 B](https://example.com/b)\n",
        )
        self.write(
            "weekly/2026-W37.md",
            "# 2026-W37 新闻趋势周报\n\n> 覆盖最近 7 天简报，共 11 篇。\n",
        )
        self.write(
            "alerts/2026-09-11.md",
            "# 2026-09-11 突发与重要更新\n\n## 09:10 突发提醒\n\n"
            "- [第一条](https://example.com/1)\n\n## 10:25 突发提醒\n\n"
            "- [第二条](https://example.com/2)\n",
        )

        entries = collect_entries(self.root)

        self.assertEqual([entry.kind for entry in entries], ["weekly", "alert", "digest"])
        by_kind = {entry.kind: entry for entry in entries}
        self.assertEqual(by_kind["digest"].generated_time, "08:02")
        self.assertEqual(by_kind["digest"].article_count, 2)
        self.assertEqual(by_kind["digest"].period_name, "早间新闻简报")
        self.assertEqual(by_kind["weekly"].publication_date.isoformat(), "2026-09-13")
        self.assertEqual(by_kind["weekly"].generated_time, "20:00")
        self.assertEqual(by_kind["weekly"].article_count, 11)
        self.assertEqual(by_kind["alert"].generated_time, "10:25")
        self.assertEqual(by_kind["alert"].article_count, 2)

    def test_builds_grouped_filterable_safe_dependency_free_html(self):
        self.write(
            "2026-09/2026-09-10-1230-noon_digest.md",
            "# <script>alert('title')</script> 午间新闻简报\n\n"
            "> 生成时间：2026-09-10 12:30｜共 1 篇\n\n"
            "1. [新闻](https://example.com)\n",
        )
        self.write(
            "alerts/2026-09-10.md",
            "# 突发 & 更新\n\n## 12:45 突发提醒\n\n- [事件](https://example.com)\n",
        )

        output = build_index(
            self.root, datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)
        )
        document = output.read_text(encoding="utf-8")

        self.assertIn("2026年9月10日 · 周四", document)
        self.assertEqual(document.count('class="date-group"'), 1)
        self.assertIn('data-filter="digest"', document)
        self.assertIn('data-filter="weekly"', document)
        self.assertIn('data-filter="alert"', document)
        self.assertIn('data-archive-kind="digest"', document)
        self.assertIn("阅读 Markdown", document)
        self.assertIn("localStorage.setItem('trendradar-theme'", document)
        self.assertIn("prefers-reduced-motion", document)
        self.assertIn('class="brand" href="../"', document)
        self.assertIn('class="home-link" href="../"', document)
        self.assertNotIn('href="/"', document)
        self.assertNotIn("<script>alert('title')</script>", document)
        self.assertIn("&lt;script&gt;alert(&#x27;title&#x27;)&lt;/script&gt;", document)
        self.assertNotIn("html2canvas", document)
        self.assertNotIn("https://cdn", document)

    def test_escapes_malicious_filename_in_markdown_links(self):
        self.write(
            "2026-09/2026-09-10-2000-evening_digest&tracking=bad.md",
            "# 晚间简报\n\n> 共 1 篇\n",
        )

        document = build_index(self.root).read_text(encoding="utf-8")

        self.assertNotIn("evening_digest&tracking=bad.md", document)
        self.assertIn("evening_digest%26tracking%3Dbad.md", document)

    def test_empty_archive_has_clear_state_and_zero_counts(self):
        document = build_index(self.root).read_text(encoding="utf-8")

        self.assertIn("暂无简报。首期生成后会出现在这里。", document)
        self.assertIn(
            'data-filter="all" aria-pressed="true">全部<span class="filter-count">0',
            document,
        )


if __name__ == "__main__":
    unittest.main()
