"""Behavioral tests for the public news workspace."""

import json
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from trendradar.core.scheduler import Scheduler
from trendradar.digest import DigestEngine, HomepageSnapshot
from trendradar.digest.engine import PublicDigest, safe_http_url
from trendradar.report.html import (
    _safe_json_data,
    render_html_content,
    write_summaries_sidecar,
)


def article(index, feed="tech", *, title=None, url=None, published=None, summary=None):
    return {
        "title": title or f"Article {index}",
        "url": url or f"https://example.com/{feed}/{index}",
        "feed_id": feed,
        "feed_name": feed.upper(),
        "summary": summary or f"Summary {index}",
        "published_at": published or f"2026-09-10T{index % 24:02d}:00:00+08:00",
    }


class HomepageDataTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {
            "ENABLED": True,
            "MAX_ITEMS": 20,
            "SUMMARY_MAX_CHARS": 100,
            "SOURCE_LIMIT": 20,
            "DEDUP_SIMILARITY": 1.0,
            "ARCHIVE_DIR": str(Path(self.temp.name) / "briefings"),
            "RETENTION_DAYS": 30,
            "SLOT_KEYS": ["morning_digest", "noon_digest", "evening_digest"],
            "SLOT_NAMES": {
                "morning_digest": "早间新闻简报",
                "noon_digest": "午间新闻简报",
                "evening_digest": "晚间新闻简报",
            },
            "CATEGORIES": [
                {"ID": "tech", "NAME": "科技与 AI", "QUOTA": 20, "WEIGHT": 1.0, "FEEDS": ["tech", "mirror"], "KEYWORDS": []},
            ],
            "BREAKING": {"ENABLED": True, "IMMEDIATE_PUSH": True, "MAX_ITEMS": 3, "COOLDOWN_MINUTES": 180, "STRONG_KEYWORDS": ["突发"]},
            "WEEKLY": {"ENABLED": False},
        }
        self.morning = datetime(2026, 9, 10, 8, 0, tzinfo=timezone(timedelta(hours=8)))

    def tearDown(self):
        self.temp.cleanup()

    def test_latest_digest_survives_refresh_and_updates_are_separate(self):
        first_items = [article(index) for index in range(20)]
        first = DigestEngine(self.config, self.morning)
        result = first.process(first_items, "morning_digest", True)
        self.assertEqual(result.period_key, "morning_digest")

        later = self.morning + timedelta(hours=1)
        newest = article(40, title="Later report", published=later.isoformat())
        refreshed = DigestEngine(self.config, later)
        self.assertIsNone(refreshed.process([newest], None, False))
        snapshot = refreshed.build_homepage_snapshot([newest])

        self.assertEqual(snapshot.latest_digest.period_key, "morning_digest")
        self.assertEqual(snapshot.latest_digest.article_count, 20)
        self.assertEqual([item["title"] for item in snapshot.updates_since_digest], ["Later report"])
        self.assertEqual(snapshot.updates_since_digest[0]["status"], "new")

        old_and_new = refreshed.build_homepage_snapshot([first_items[0], newest])
        self.assertEqual(old_and_new.all_news[0]["status"], "new")
        self.assertEqual(old_and_new.all_news[1]["status"], "")

    def test_all_news_keeps_cross_source_items_and_rejects_unsafe_urls(self):
        now = self.morning + timedelta(hours=1)
        engine = DigestEngine(self.config, now)
        source_items = [
            article(1, "tech", title="Same report", url="https://example.com/shared"),
            article(1, "mirror", title="Same report", url="https://example.com/shared"),
            article(2, "tech", title="Unsafe", url="javascript:alert(1)"),
        ]
        engine.process(source_items, None, False)
        snapshot = engine.build_homepage_snapshot(source_items)
        self.assertEqual(len(snapshot.all_news), 2)
        self.assertEqual({item["source_name"] for item in snapshot.all_news}, {"TECH", "MIRROR"})
        self.assertEqual(safe_http_url("javascript:alert(1)"), "")


def make_homepage_snapshot(count=85):
    """Shared fixture: a snapshot with `count` current articles and a 1-article digest."""

    items = [
        {
            "title": f"Current article {index}",
            "url": f"https://example.com/current/{index}",
            "summary": f"Current summary {index}",
            "source_name": "Source A" if index % 2 else "Source B",
            "published_at": f"2026-09-10T{index % 24:02d}:00:00+08:00",
            "category_id": "tech",
            "category_name": "科技与 AI",
            "status": "new",
            "first_seen": "private timestamp",
            "internal_id": "secret-id",
        }
        for index in range(count)
    ]
    digest = PublicDigest(
        created_at="2026-09-10T08:00:00+08:00",
        period_key="morning_digest",
        period_name="早间新闻简报",
        archive_url="briefings/2026-09/2026-09-10-0800-morning_digest.md",
        sections=[
            {"name": "科技与 AI", "count": 1, "articles": [{
                "title": "Digest article",
                "url": "https://example.com/digest",
                "summary": "Digest summary",
                "source_name": "Source A",
                "published_at": "2026-09-10T07:30:00+08:00",
                "status": "更新",
            }]},
            {"name": "全球事务", "count": 0, "articles": []},
        ],
        article_count=1,
        source_count=1,
    )
    return HomepageSnapshot(
        generated_at="2026-09-10T09:00:00+08:00",
        next_slot={"key": "noon_digest", "name": "午间新闻简报", "start": "12:30", "at": "2026-09-10T12:30:00+08:00"},
        slots=[
            {"key": "morning_digest", "name": "早间新闻简报", "start": "08:00", "active": False},
            {"key": "noon_digest", "name": "午间新闻简报", "start": "12:30", "active": False, "next": True},
            {"key": "evening_digest", "name": "晚间新闻简报", "start": "20:00", "active": False},
        ],
        latest_digest=digest,
        active_alerts=[],
        updates_since_digest=items[:2],
        all_news=items,
        source_count=2,
    )


class HomepageHtmlTest(unittest.TestCase):
    def make_snapshot(self, count=85):
        return make_homepage_snapshot(count)

    def test_workspace_has_digest_controls_and_safe_public_payload(self):
        snapshot = self.make_snapshot()
        snapshot.all_news[0].update({
            "title": "</script><script>alert(1)</script>\u2028next",
            "url": "javascript:alert(1)",
            "archive_path": "C:/private/.state.json",
        })
        document = render_html_content({}, 0, homepage_snapshot=snapshot)

        self.assertIn('id="digest"', document)
        self.assertIn('id="all-news"', document)
        self.assertIn('id="news-search"', document)
        self.assertIn('id="load-more"', document)
        self.assertIn('id="app-sidebar"', document)
        self.assertIn('data-sidebar-toggle', document)
        self.assertIn("trendradar-sidebar-collapsed", document)
        self.assertIn('data-theme-toggle', document)
        self.assertIn(':root[data-theme="dark"]', document)
        self.assertNotIn("__WORKSPACE_", document)
        self.assertEqual(document.count("function syncTheme()"), 1)
        self.assertEqual(document.count("function toggleSidebar()"), 1)
        self.assertNotIn("ui-serif", document)
        self.assertIn("var PAGE_SIZE = 40", document)
        self.assertIn("briefings/2026-09/", document)
        self.assertIn('href="briefings/2026-09/2026-09-10-0800-morning_digest.html"', document)
        self.assertIn('href="briefings/2026-09/2026-09-10-0800-morning_digest.md" download', document)
        self.assertNotIn('href="/briefings/', document)
        self.assertNotIn("</script><script>alert(1)</script>", document)
        self.assertNotIn("javascript:alert(1)", document)
        self.assertNotIn("private timestamp", document)
        self.assertNotIn("secret-id", document)
        self.assertNotIn("archive_path", document)
        self.assertIn("\\u003c/script\\u003e", document)
        self.assertIn("\\u2028", document)

    def test_no_digest_empty_state_names_next_slot(self):
        snapshot = self.make_snapshot(1)
        snapshot.latest_digest = None
        snapshot.updates_since_digest = []
        document = render_html_content({}, 0, homepage_snapshot=snapshot)
        self.assertIn("首期简报将在 12:30 生成", document)
        self.assertIn('id="updates-nav" href="#updates" hidden', document)

    def test_json_serializer_blocks_raw_text_breakout(self):
        encoded = _safe_json_data({"x": "</script>&\u2028\u2029"})
        self.assertEqual(json.loads(encoded)["x"], "</script>&\u2028\u2029")
        self.assertNotIn("<", encoded)
        self.assertNotIn("&", encoded)
        self.assertIn("\\u2028", encoded)
        self.assertIn("\\u2029", encoded)


class HomepagePayloadShapeTest(unittest.TestCase):
    """The payload is split for weight; these pin the contract the client relies on."""

    def setUp(self):
        self.snapshot = make_homepage_snapshot()

    def payload(self, document):
        match = re.search(r'<script id="homepage-data"[^>]*>(.*?)</script>', document, re.S)
        self.assertIsNotNone(match, "homepage-data block is missing")
        return json.loads(match.group(1))

    def summaries(self, document):
        match = re.search(r'<script id="summaries-data"[^>]*>(.*?)</script>', document, re.S)
        self.assertIsNotNone(match, "summaries-data block is missing")
        return json.loads(match.group(1))

    def test_summary_is_not_in_the_all_news_items(self):
        document = render_html_content({}, 0, homepage_snapshot=self.snapshot)
        payload = self.payload(document)

        self.assertTrue(payload["allNews"])
        for item in payload["allNews"]:
            self.assertNotIn("summary", item, "summaries must not travel inline in allNews")

    def test_summaries_align_with_all_news_by_position(self):
        document = render_html_content({}, 0, homepage_snapshot=self.snapshot)
        payload = self.payload(document)
        summaries = self.summaries(document)

        self.assertEqual(len(summaries), len(payload["allNews"]))
        self.assertEqual(summaries[0], "Current summary 0")
        self.assertEqual(summaries[7], "Current summary 7")

    def test_sidecar_matches_the_inline_copy(self):
        document = render_html_content({}, 0, homepage_snapshot=self.snapshot)
        inline = self.summaries(document)

        with tempfile.TemporaryDirectory() as temp:
            path = write_summaries_sidecar(temp, self.snapshot, None)
            sidecar = json.loads(Path(path).read_text(encoding="utf-8"))

        self.assertEqual(inline, sidecar)
        self.assertTrue(path.endswith("briefings-summaries.json"))

    def test_source_and_category_names_ship_as_lookup_indices(self):
        document = render_html_content({}, 0, homepage_snapshot=self.snapshot)
        payload = self.payload(document)

        self.assertEqual(sorted(payload["sources"]), ["Source A", "Source B"])
        for item in payload["allNews"]:
            self.assertNotIn("source_name", item)
            self.assertNotIn("category_name", item)
            index = int(item["title"].rsplit(" ", 1)[1])
            expected = "Source A" if index % 2 else "Source B"
            self.assertEqual(payload["sources"][item["_si"]], expected)

    def test_category_lookup_covers_every_item(self):
        document = render_html_content({}, 0, homepage_snapshot=self.snapshot)
        payload = self.payload(document)

        for item in payload["allNews"]:
            self.assertLess(item["_ci"], len(payload["categories"]))
            self.assertTrue(payload["categories"][item["_ci"]])

    def test_updates_ship_as_positions_not_duplicated_objects(self):
        document = render_html_content({}, 0, homepage_snapshot=self.snapshot)
        payload = self.payload(document)

        # make_snapshot sets updates_since_digest to the first two articles.
        self.assertEqual(payload["updates"], [0, 1])
        for index in payload["updates"]:
            self.assertIsInstance(index, int)
            self.assertLess(index, len(payload["allNews"]))

    def test_updates_are_empty_without_a_snapshot(self):
        document = render_html_content({}, 0, rss_items=None)
        self.assertEqual(self.payload(document)["updates"], [])


    def test_empty_sections_do_not_render_filter_chips(self):
        """A section with nothing in it is not a useful filter."""
        snapshot = self.snapshot
        # make_homepage_snapshot gives 全球事务 count 0 and 科技与 AI count 1.
        document = render_html_content({}, 0, homepage_snapshot=snapshot)

        self.assertIn("科技与 AI", document)
        self.assertNotIn('data-category="全球事务"', document)
        # The empty section is still listed in the payload's category options.
        self.assertIn("全球事务", document)

    def test_empty_sections_do_not_render_sidebar_categories(self):
        snapshot = self.snapshot
        document = render_html_content({}, 0, homepage_snapshot=snapshot)
        sidebar = document.split('class="sidebar-categories"', 1)[1].split("</div>", 1)[0]

        self.assertIn("科技与 AI", sidebar)
        self.assertNotIn("全球事务", sidebar)


class SchedulerPublicationTest(unittest.TestCase):
    def test_publication_schedule_reports_three_slots_and_next_one(self):
        timeline = yaml.safe_load(Path("config/timeline.yaml").read_text(encoding="utf-8"))
        now = datetime(2026, 9, 10, 12, 31, tzinfo=timezone(timedelta(hours=8)))
        scheduler = Scheduler({"enabled": True, "preset": "news_digest"}, timeline, object(), lambda: now)
        schedule = scheduler.publication_schedule(["morning_digest", "noon_digest", "evening_digest"])
        self.assertEqual([slot["start"] for slot in schedule["slots"]], ["08:00", "12:30", "20:00"])
        self.assertEqual(schedule["next_slot"]["key"], "evening_digest")
        self.assertEqual(schedule["next_slot"]["at"], "2026-09-10T20:00:00+08:00")
        self.assertTrue(next(slot["next"] for slot in schedule["slots"] if slot["key"] == "evening_digest"))


class WorkbenchInformationArchitectureTest(unittest.TestCase):
    """The workbench IA: briefing first, post-briefing queue, folded 运行概览, ledger."""

    def setUp(self):
        self.snapshot = make_homepage_snapshot()
        self.document = render_html_content({}, 0, homepage_snapshot=self.snapshot)

    def payload(self, document=None):
        match = re.search(r'<script id="homepage-data"[^>]*>(.*?)</script>', document or self.document, re.S)
        self.assertIsNotNone(match, "homepage-data block is missing")
        return json.loads(match.group(1))

    def test_each_region_of_the_architecture_renders(self):
        for marker in (
            'id="kpis"', 'id="cadence"', 'id="sparkLine"', 'id="feed"', 'id="queueList"',
            'id="updates"', 'id="all-news"', 'id="db"', 'id="results-count"', 'id="sheet"',
            'id="provenance"', 'id="news-search"', 'id="news-category"', 'id="news-state"',
            'id="news-sort"', 'id="load-more"', 'id="autoBtn"', 'id="exportBtn"',
            'id="refreshBtn"', 'id="livePill"', 'id="nextCrawl"', 'id="nextDigest"',
        ):
            self.assertIn(marker, self.document)
        for fn in ("function renderKpi(", "function renderSpark(", "function renderFeed(",
                   "function renderQueue(", "function renderRows(", "function toMarkdown("):
            self.assertIn(fn, self.document)
        self.assertIn("var PAGE_SIZE = 40", self.document)

    def test_the_page_opens_on_the_briefing_not_the_dashboard(self):
        """The dashboard is a folded disclosure: the first screen is news."""

        position = {
            name: self.document.index(marker)
            for name, marker in (
                ("meta", 'class="page-meta"'),
                ("briefing", 'id="digest"'),
                ("queue", 'id="updates"'),
                ("overview", ' id="overview"'),
                ("ledger", 'id="all-news"'),
            )
        }
        self.assertEqual(
            sorted(position, key=position.get),
            ["meta", "briefing", "queue", "overview", "ledger"],
        )
        # Closed by default, and nothing the dashboard owns escaped the fold.
        self.assertIn('<details class="overview" id="overview">', self.document)
        self.assertNotIn("<details class=\"overview\" id=\"overview\" open", self.document)
        folded = self.document.split(' id="overview"', 1)[1].split("</details>", 1)[0]
        for marker in ('id="kpis"', 'id="cadence"', 'id="sparkLine"', 'id="feed"',
                       'id="provenance"', 'id="nextCrawlAt"'):
            self.assertIn(marker, folded)
        # The top bar already names the workspace, so the page has one <h1>.
        self.assertNotIn("page-title", self.document)
        self.assertEqual(self.document.count("<h1"), 1)

    def test_no_template_marker_survives_into_the_page(self):
        self.assertEqual(re.findall(r"__[A-Z][A-Z_]+__", self.document), [])

    def test_ledger_row_template_matches_the_header_columns(self):
        head = self.document.split('<div class="db-head">', 1)[1].split('<div class="db-more">', 1)[0]
        for label in ("读", "标题", "板块", "来源", "发布时间", "状态"):
            self.assertIn(label, head)
        row_fn = self.document.split("function rowHtml(x) {", 1)[1].split("function renderRows()", 1)[0]
        self.assertEqual(row_fn.count('class="db-cell'), 6)

    def test_payload_carries_the_liveness_facts(self):
        payload = self.payload()
        self.assertEqual(payload["generatedAt"], "2026-09-10T09:00:00+08:00")
        self.assertEqual(payload["generatedLabel"], "2026-09-10 09:00")
        self.assertEqual(payload["staleAfter"], 90)
        self.assertEqual(payload["refreshSeconds"], 1800)

    def test_category_indices_survive_the_option_list_reorder(self):
        """The dropdown is ordered by the digest; every ``_ci`` must be remapped."""

        snapshot = make_homepage_snapshot(count=4)
        snapshot.all_news = [
            {
                "title": f"row {index}",
                "url": f"https://example.com/{index}",
                "summary": "",
                "published_at": f"2026-09-10T0{index}:00:00+08:00",
                "category_id": "b" if index % 2 == 0 else "a",
                "category_name": "B 板块" if index % 2 == 0 else "A 板块",
                "status": "new",
            }
            for index in range(4)
        ]
        # Same two names, opposite order: first appearance (B, A) vs digest order (A, B).
        snapshot.latest_digest.sections = [
            {"name": "A 板块", "count": 1, "quota": 3, "articles": []},
            {"name": "B 板块", "count": 1, "quota": 1, "articles": []},
        ]
        payload = self.payload(render_html_content({}, 0, homepage_snapshot=snapshot))

        self.assertEqual(payload["categories"][:2], ["A 板块", "B 板块"])
        for item in payload["allNews"]:
            index = int(item["title"].rsplit(" ", 1)[1])
            expected = "B 板块" if index % 2 == 0 else "A 板块"
            self.assertEqual(payload["categories"][item["_ci"]], expected)

    def test_digest_reads_as_category_groups_with_quota(self):
        self.snapshot.latest_digest.sections[0]["quota"] = 6
        document = render_html_content({}, 0, homepage_snapshot=self.snapshot)

        self.assertIn('class="digest-group" data-category="科技与 AI"', document)
        self.assertIn('class="digest-group-head"', document)
        self.assertIn("配额 6 · 入选 1", document)
        self.assertIn('class="status-badge status-更新"', document)
        # Numbering restarts inside each group instead of running across the issue.
        self.assertIn('<span class="article-number" aria-hidden="true">01</span>', document)
        self.assertNotIn("digest-table-head", document)

    def test_provenance_states_where_the_numbers_come_from(self):
        self.assertIn("数据面为 2026-09-10 09:00 的线上抓取快照", self.document)
        self.assertIn("台账 85 条 · 2 个来源 · 2 个板块", self.document)
        self.assertIn("相对最近一期简报", self.document)
        self.assertIn("发布时间由各源 RSS 提供、不是采集时间", self.document)

    def test_stated_cadence_matches_the_deployment(self):
        """Copy that states a deployment fact must not drift away from it."""

        from trendradar.report import html as html_module

        timer = Path("deployment/trendradar-collect.timer").read_text(encoding="utf-8")
        self.assertIn("OnCalendar=*-*-* *:00,30:00", timer)
        config = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["rss"]["freshness_filter"]["max_age_days"], 7)

        self.assertEqual(html_module.REFRESH_SECONDS, 1800)
        self.assertEqual(html_module.STALE_AFTER_MINUTES, 90)
        self.assertIn("每 30 分钟 · :00 / :30", self.document)
        self.assertIn("全局 7 天", self.document)
        self.assertIn("08:00 · 12:30 · 20:00", self.document)

    def test_palette_type_and_accent_come_only_from_the_shared_theme(self):
        # The only literals are the two browser theme-colour hints, which mirror --bg.
        self.assertEqual(sorted(set(re.findall(r"#[0-9a-fA-F]{3,6}\b", self.document))), ["#15181c", "#fbfcfd"])
        # The bright accent is a graphical mark (chart line/dots, live pill) only;
        # every piece of accent-coloured text uses the darker --accent-ink.
        self.assertEqual(len(re.findall(r"var\(--accent\)", self.document)), 3)
        self.assertNotIn("color: var(--accent);", self.document)
        self.assertIn("var(--accent-ink)", self.document)

    def test_no_serif_and_chinese_never_triggers_a_font_download(self):
        self.assertNotIn("serif", self.document.replace("sans-serif", ""))
        # Latin and digits only: 7 subset faces, each range-bounded.
        self.assertEqual(self.document.count("@font-face"), 7)
        self.assertEqual(self.document.count("unicode-range:"), 7)
        self.assertNotIn("U+4E00", self.document)

        ui_stack = self.document.split("--font-ui:", 1)[1].split(";", 1)[0]
        mono_stack = self.document.split("--font-mono:", 1)[1].split(";", 1)[0]
        self.assertTrue(ui_stack.rstrip().endswith("sans-serif"), ui_stack)
        self.assertTrue(mono_stack.rstrip().endswith("sans-serif"), mono_stack)
        self.assertIn("Microsoft YaHei", ui_stack)
        # A generic monospace tail resolves to Songti on a Chinese Windows box.
        self.assertNotIn("ui-monospace,monospace", mono_stack)
        self.assertIn("Cascadia Mono", mono_stack)


if __name__ == "__main__":
    unittest.main()
