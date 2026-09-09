"""Behavioral tests for scheduled briefings, deduplication and archives."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trendradar.digest import DigestEngine
from trendradar.digest.engine import canonical_url, clean_summary
from trendradar.notification.splitter import _format_digest_summary


def item(index, feed, title=None, summary=None, url=None):
    return {
        "title": title or f"{feed} article {index} about an important development",
        "url": url or f"https://example.com/{feed}/{index}?utm_source=rss",
        "feed_id": feed,
        "feed_name": feed.upper(),
        "summary": summary or f"Summary for article {index}",
        "published_at": f"2026-09-09T0{index % 9}:00:00+00:00",
    }


class DigestEngineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {
            "ENABLED": True,
            "MAX_ITEMS": 20,
            "SUMMARY_MAX_CHARS": 100,
            "SOURCE_LIMIT": 2,
            "DEDUP_SIMILARITY": 0.88,
            "ARCHIVE_DIR": str(Path(self.temp.name) / "briefings"),
            "RETENTION_DAYS": 30,
            "SLOT_KEYS": ["morning_digest", "evening_digest"],
            "SLOT_NAMES": {"morning_digest": "早间新闻简报"},
            "CATEGORIES": [
                {"ID": "tech", "NAME": "科技与 AI", "QUOTA": 6, "WEIGHT": 1.6,
                 "FEEDS": ["tech1", "tech2", "tech3"], "KEYWORDS": []},
                {"ID": "games", "NAME": "游戏", "QUOTA": 4, "WEIGHT": 1.45,
                 "FEEDS": ["game1", "game2"], "KEYWORDS": []},
                {"ID": "culture", "NAME": "社会与文化", "QUOTA": 4, "WEIGHT": 1.35,
                 "FEEDS": ["culture1", "culture2"], "KEYWORDS": []},
                {"ID": "world", "NAME": "全球事务", "QUOTA": 6, "WEIGHT": 1.0,
                 "FEEDS": ["world1", "world2", "world3"], "KEYWORDS": []},
            ],
            "BREAKING": {
                "ENABLED": True, "IMMEDIATE_PUSH": True, "MAX_ITEMS": 3,
                "COOLDOWN_MINUTES": 180, "STRONG_KEYWORDS": ["breaking:", "地震"],
            },
            "WEEKLY": {"ENABLED": True, "WEEKDAY": 7, "SLOT_KEY": "evening_digest"},
        }
        self.now = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def test_selects_twenty_with_larger_preferred_sections_and_writes_markdown(self):
        subjects = [
            "quantum processor benchmark", "robotics safety framework", "semiconductor supply agreement",
            "independent studio acquisition", "console launch schedule", "role playing expansion",
            "public health investigation", "museum restitution decision", "education access study",
            "regional election result", "trade negotiation outcome", "ceasefire monitoring mission",
        ]
        items = []
        for feed_index, feed in enumerate(("tech1", "tech2", "tech3", "game1", "game2", "culture1", "culture2", "world1", "world2", "world3")):
            items.extend(
                item(index, feed, title=f"{subjects[(feed_index + index) % len(subjects)]} {feed} report {index}")
                for index in range(3)
            )
        selection_config = dict(self.config, DEDUP_SIMILARITY=1.0)
        result = DigestEngine(selection_config, self.now).process(items, "morning_digest", True)

        self.assertIsNotNone(result)
        self.assertEqual(len(result.articles), 20)
        counts = {stat["word"]: stat["count"] for stat in result.stats}
        self.assertGreaterEqual(counts["科技与 AI"], 6)
        self.assertGreaterEqual(counts["游戏"], 4)
        self.assertGreaterEqual(counts["社会与文化"], 4)
        archive = Path(result.archive_path)
        self.assertTrue(archive.exists())
        content = archive.read_text(encoding="utf-8")
        self.assertIn("# 2026-09-09 早间新闻简报", content)
        self.assertIn("简介：", content)
        self.assertIn("https://example.com/", content)

    def test_deduplicates_tracking_urls_titles_and_near_copies(self):
        base = item(1, "tech1", title="A major artificial intelligence system launches today",
                    url="https://example.com/story?id=1&utm_source=feed")
        items = [
            base,
            item(2, "tech2", title="Syndicated alternate title", url="https://example.com/story?gclid=x&id=1"),
            item(3, "world1", title=" A MAJOR artificial intelligence system launches today "),
            item(4, "world2", title="A major artificial intelligence system launches today!"),
        ]
        result = DigestEngine(self.config, self.now).process(items, "morning_digest", True)
        self.assertEqual(len(result.articles), 1)
        self.assertEqual(canonical_url(base["url"]), "https://example.com/story?id=1")

    def test_summary_limit_and_breaking_alert_retry_until_delivery(self):
        long_summary = "这是一条很长的新闻简介" * 20
        breaking = item(1, "world1", title="Breaking: major earthquake", summary=long_summary)
        engine = DigestEngine(self.config, self.now)
        result = engine.process([breaking], None, False)
        self.assertEqual(result.kind, "alert")
        self.assertTrue(result.force_push)
        self.assertLessEqual(len(result.articles[0]["summary"]), 100)
        self.assertEqual(clean_summary(long_summary, 100)[-1], "…")

        retry = DigestEngine(self.config, self.now + timedelta(minutes=30)).process([breaking], None, False)
        self.assertEqual(retry.result_id, result.result_id)
        engine.mark_delivered(result)
        no_retry = DigestEngine(self.config, self.now + timedelta(minutes=31)).process([breaking], None, False)
        self.assertIsNone(no_retry)

    def test_content_change_is_available_to_next_digest_as_update(self):
        original = item(1, "tech1", summary="Original summary")
        first = DigestEngine(self.config, self.now).process([original], "morning_digest", True)
        changed = dict(original, summary="Materially revised summary")
        later = self.now + timedelta(hours=4, minutes=30)
        second = DigestEngine(self.config, later).process([changed], "evening_digest", True)
        self.assertEqual(len(second.articles), 1)
        self.assertEqual(second.articles[0]["status"], "updated")
        self.assertEqual(second.stats[0]["titles"][0]["digest_status"], "更新")

    def test_sunday_evening_writes_weekly_trend_report(self):
        sunday = datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc)
        result = DigestEngine(self.config, sunday).process(
            [item(1, "tech1"), item(2, "culture1")], "evening_digest", True
        )
        self.assertIsNotNone(result)
        weekly = Path(self.temp.name) / "briefings" / "weekly" / "2026-W37.md"
        self.assertTrue(weekly.exists())
        content = weekly.read_text(encoding="utf-8")
        self.assertIn("板块趋势", content)
        self.assertIn("科技与 AI", content)

    def test_unchanged_observation_does_not_rewrite_state_and_summary_renders(self):
        article = item(1, "tech1")
        first = DigestEngine(self.config, self.now)
        self.assertIsNone(first.process([article], None, False))
        state_path = Path(self.config["ARCHIVE_DIR"]) / ".state.json"
        original = state_path.read_bytes()
        second = DigestEngine(self.config, self.now + timedelta(minutes=30))
        self.assertIsNone(second.process([article], None, False))
        self.assertEqual(original, state_path.read_bytes())
        self.assertIn("简介：", _format_digest_summary({"summary": "短简介"}, "telegram"))


if __name__ == "__main__":
    unittest.main()
