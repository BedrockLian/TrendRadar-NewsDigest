"""Tests for localising the workspace through the briefing engine."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trendradar.digest import DigestEngine

from tests.test_digest import item


class StubTranslation:
    def __init__(self, translated_text="", success=True):
        self.translated_text = translated_text
        self.original_text = ""
        self.success = success
        self.error = ""


class StubBatch:
    def __init__(self, results):
        self.results = results
        self.success_count = len(results)
        self.fail_count = 0
        self.total_count = len(results)


class StubTranslator:
    """Stands in for AITranslator; records every call so caching is observable."""

    def __init__(self, enabled=True, prefix="【译】"):
        self.enabled = enabled
        self.prefix = prefix
        self.calls = []
        self.target_language = "简体中文"

    def translate_batch(self, texts):
        self.calls.append(list(texts))
        return StubBatch([StubTranslation(f"{self.prefix}{text}") for text in texts])


class FailOnceTranslator(StubTranslator):
    def __init__(self):
        super().__init__()
        self.failures = 0

    def translate_batch(self, texts):
        self.failures += 1
        if self.failures == 1:
            raise RuntimeError("upstream 500")
        return super().translate_batch(texts)


class TranslationTest(unittest.TestCase):
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
            "SLOT_KEYS": ["morning_digest"],
            "SLOT_NAMES": {"morning_digest": "早间新闻简报"},
            "CATEGORIES": [
                {"ID": "tech", "NAME": "科技与 AI", "QUOTA": 6, "WEIGHT": 1.6,
                 "FEEDS": ["tech1", "tech2"], "KEYWORDS": []},
            ],
            "BREAKING": {"ENABLED": True, "IMMEDIATE_PUSH": True, "MAX_ITEMS": 3,
                         "COOLDOWN_MINUTES": 180, "STRONG_KEYWORDS": []},
            "WEEKLY": {"ENABLED": False, "WEEKDAY": 7, "SLOT_KEY": "evening_digest"},
            "TRANSLATION": {"BATCH_SIZE": 10, "MAX_NEW_PER_RUN": 50},
        }
        self.now = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def make_items(self, count=4):
        """Distinct stories: item() keys article identity on feed + index.

        Subjects are deliberately dissimilar.  The engine's near-duplicate guard
        merges titles that differ by a single character once they exceed the
        similarity ratio, so a lettered series would collapse into one story.
        """
        subjects = [
            "Wireless chip breakthrough announced by researchers",
            "Regulator opens inquiry into cloud billing practices",
            "Open source model released under a permissive licence",
            "Data centre power demand reshapes grid planning",
            "Handset maker delays its foldable launch window",
            "Compiler team ships a faster garbage collector",
            "Undersea cable outage affects three regions",
            "Standards body ratifies a new video codec",
            "Retailer pilots drone delivery in rural counties",
            "Hospital network migrates records to a new platform",
            "Satellite operator expands its ground station fleet",
            "Battery chemistry shift lowers pack costs",
            "Panel maker reports a yield improvement",
            "Search engine adds on-device indexing",
            "Robotics lab demonstrates a bipedal stair climb",
            "Weather service upgrades its forecast model",
        ]
        return [
            item(i, "tech1", title=subjects[i % len(subjects)],
                 summary=f"Reporters describe a distinct development in brief {i}")
            for i in range(count)
        ]

    def test_without_a_translator_nothing_changes(self):
        engine = DigestEngine(self.config, self.now)
        engine.process(self.make_items(), None, False)
        snapshot = engine.build_homepage_snapshot([])

        self.assertFalse((Path(self.temp.name) / "briefings" / ".translations.json").exists())
        self.assertEqual(snapshot.all_news, [])

    def test_disabled_translator_is_ignored(self):
        translator = StubTranslator(enabled=False)
        engine = DigestEngine(self.config, self.now, translator=translator)
        engine.process(self.make_items(), None, False)

        self.assertEqual(translator.calls, [])

    def test_titles_and_summaries_are_localised_in_the_workbench(self):
        translator = StubTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        items = self.make_items(4)
        engine.process(items, None, False)

        snapshot = engine.build_homepage_snapshot(items)
        self.assertTrue(snapshot.all_news)
        for article in snapshot.all_news:
            self.assertTrue(article["title"].startswith("【译】"), article["title"])
            self.assertTrue(article["summary"].startswith("【译】"), article["summary"])

    def test_translations_are_cached_across_runs(self):
        translator = StubTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        items = self.make_items(4)
        engine.process(items, None, False)
        first_round = sum(len(call) for call in translator.calls)
        self.assertEqual(first_round, 8, "4 titles + 4 summaries on the first run")

        # A second crawl reporting the same stories must not hit the API again.
        DigestEngine(self.config, self.now, translator=translator).process(items, None, False)
        self.assertEqual(
            sum(len(call) for call in translator.calls), first_round,
            "unchanged content must be served from the cache",
        )

    def test_changed_content_is_retranslated(self):
        translator = StubTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        engine.process(self.make_items(2), None, False)
        before = sum(len(call) for call in translator.calls)

        revised = self.make_items(2)
        revised[0]["summary"] = "A completely different follow-up summary"
        DigestEngine(self.config, self.now, translator=translator).process(revised, None, False)

        self.assertGreater(
            sum(len(call) for call in translator.calls), before,
            "a material content change must be translated again",
        )

    def test_already_chinese_content_is_not_sent_to_the_api(self):
        translator = StubTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        engine.process(
            [item(1, "tech1", title="国产芯片取得突破", summary="工程师介绍了新方案")],
            None,
            False,
        )

        self.assertEqual(translator.calls, [])
        article = next(iter(engine.state["articles"].values()))
        # The decision is cached by content hash; the record itself stays lean.
        entry = engine.translation_cache["entries"][article["content_hash"]]
        self.assertEqual(entry["title_zh"], "国产芯片取得突破")

    def test_translation_failure_keeps_the_original_text(self):
        translator = FailOnceTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        items = self.make_items(2)
        engine.process(items, None, False)

        snapshot = engine.build_homepage_snapshot(items)
        self.assertTrue(snapshot.all_news)
        for article in snapshot.all_news:
            self.assertFalse(article["title"].startswith("【译】"))
            self.assertTrue(article["title"])

    def test_missing_digest_config_does_not_break_translation(self):
        translator = StubTranslator()
        config = dict(self.config)
        config.pop("TRANSLATION", None)
        engine = DigestEngine(config, self.now, translator=translator)
        items = self.make_items(2)
        engine.process(items, None, False)

        snapshot = engine.build_homepage_snapshot(items)
        self.assertTrue(snapshot.all_news[0]["title"].startswith("【译】"))

    def test_cache_is_a_separate_file_from_state(self):
        translator = StubTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        engine.process(self.make_items(2), None, False)

        archive = Path(self.temp.name) / "briefings"
        self.assertTrue((archive / ".translations.json").is_file())
        self.assertTrue((archive / ".state.json").is_file())
        # The state ledger stays free of translation payloads.
        state_text = (archive / ".state.json").read_text(encoding="utf-8")
        self.assertNotIn("【译】", state_text)

    def test_cache_prunes_entries_with_no_live_article(self):
        translator = StubTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        engine.process(self.make_items(2), None, False)
        self.assertTrue(engine.translation_cache["entries"])

        engine.state["articles"] = {}
        engine._prune_translation_cache()

        self.assertEqual(engine.translation_cache["entries"], {})

    def test_already_translated_content_is_used_by_the_digest_too(self):
        translator = StubTranslator()
        engine = DigestEngine(self.config, self.now, translator=translator)
        items = self.make_items(3)
        result = engine.process(items, "morning_digest", True)

        self.assertIsNotNone(result)
        for stat in result.stats:
            for entry in stat.get("titles", []):
                self.assertTrue(
                    entry["title"].startswith("【译】"),
                    "the briefing projection must use the cached translation",
                )

    def test_briefing_translates_its_own_selection(self):
        """Digest articles must be translated even if the crawl pass missed them.

        The per-crawl pass is capped per run, so a story can be selected for a
        briefing before its turn came in the backfill.  The briefing is what a
        reader sees first, so it cannot depend on that ordering.
        """
        translator = StubTranslator()
        # A tiny backfill ceiling, so most of the pool is NOT translated by the
        # crawl pass; the briefing must still come out translated.
        config = dict(self.config, TRANSLATION={"BATCH_SIZE": 10, "MAX_NEW_PER_RUN": 2})
        engine = DigestEngine(config, self.now, translator=translator)
        pool = self.make_items(12)

        result = engine.process(pool, "morning_digest", True)

        self.assertIsNotNone(result)
        self.assertTrue(result.articles)
        for stat in result.stats:
            for entry in stat.get("titles", []):
                self.assertTrue(
                    entry["title"].startswith("【译】"),
                    f"briefing entry left untranslated: {entry['title']}",
                )

    def test_per_run_ceiling_bounds_api_usage(self):
        translator = StubTranslator()
        config = dict(self.config, TRANSLATION={"BATCH_SIZE": 100, "MAX_NEW_PER_RUN": 3})
        engine = DigestEngine(config, self.now, translator=translator)
        engine.process(self.make_items(20), None, False)

        # 3 records x (title + summary) = 6 texts, never all 40.
        self.assertEqual(sum(len(call) for call in translator.calls), 6)


if __name__ == "__main__":
    unittest.main()
