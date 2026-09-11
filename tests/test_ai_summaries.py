"""Tests for Chinese AI summary generation resilience."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from trendradar.digest import DigestEngine


class RefusingClient:
    """Refuses any request whose payload mentions the poisoned story."""

    def __init__(self, poison="poison"):
        self.poison = poison
        self.calls = []

    def chat(self, messages, **kwargs):
        payload = messages[-1]["content"]
        self.calls.append(payload)
        if self.poison in payload:
            raise RuntimeError(
                'BadRequestError: DeepseekException - {"error":{"message":'
                '"Content Exists Risk"}}'
            )
        import json
        import re

        requested = json.loads(payload)
        return json.dumps(
            [{"id": item["id"], "summary": f"中文简介 {item['id']}"} for item in requested],
            ensure_ascii=False,
        )


class EmptyClient:
    """Answers with an empty body, the way a filtered request does."""

    def __init__(self, poison="poison"):
        self.poison = poison
        self.calls = []

    def chat(self, messages, **kwargs):
        payload = messages[-1]["content"]
        self.calls.append(payload)
        if self.poison in payload:
            return ""
        import json

        requested = json.loads(payload)
        return json.dumps(
            [{"id": item["id"], "summary": f"中文简介 {item['id']}"} for item in requested],
            ensure_ascii=False,
        )


class AiSummaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {
            "ENABLED": True,
            "MAX_ITEMS": 20,
            "SUMMARY_MAX_CHARS": 100,
            "SOURCE_LIMIT": 2,
            "DEDUP_SIMILARITY": 1.0,
            "ARCHIVE_DIR": str(Path(self.temp.name) / "briefings"),
            "RETENTION_DAYS": 30,
            "SLOT_KEYS": ["morning_digest"],
            "SLOT_NAMES": {"morning_digest": "早间新闻简报"},
            "CATEGORIES": [],
            "BREAKING": {"ENABLED": False, "IMMEDIATE_PUSH": False, "MAX_ITEMS": 3,
                         "COOLDOWN_MINUTES": 180, "STRONG_KEYWORDS": []},
            "WEEKLY": {"ENABLED": False, "WEEKDAY": 7, "SLOT_KEY": "evening_digest"},
            "AI_SUMMARIES": {"ENABLED": True, "BATCH_SIZE": 4},
        }
        self.now = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def records(self, count=4):
        return [
            {"id": f"id{i}", "title": f"Story number {i}", "summary": f"Feed summary {i}",
             "content_hash": f"hash{i}"}
            for i in range(count)
        ]

    def engine_with(self, client):
        engine = DigestEngine(self.config, self.now)
        engine.state["articles"] = {
            r["id"]: {"id": r["id"], "title": r["title"], "summary": r["summary"],
                      "content_hash": r["content_hash"]}
            for r in self.records(8)
        }
        return engine, client

    def test_summaries_are_applied_when_the_request_succeeds(self):
        records = self.records(4)
        engine = DigestEngine(self.config, self.now)
        engine.state["articles"] = {r["id"]: dict(r) for r in records}

        with patch.object(engine, "_get_ai_client", return_value=RefusingClient()):
            engine._apply_ai_summaries(records)

        for record in records:
            self.assertTrue(record["summary"].startswith("中文简介"), record["summary"])
            self.assertEqual(engine.state["articles"][record["id"]]["summary"],
                             record["summary"])

    def test_one_refused_story_does_not_lose_the_whole_batch(self):
        """A filtered story must not cost the other stories their summary."""
        records = self.records(4)
        records[1]["title"] = "poison headline the provider refuses"
        engine = DigestEngine(self.config, self.now)
        engine.state["articles"] = {r["id"]: dict(r) for r in records}
        client = RefusingClient()

        with patch.object(engine, "_get_ai_client", return_value=client):
            engine._apply_ai_summaries(records)

        summarised = [r for r in records if r["summary"].startswith("中文简介")]
        self.assertEqual(len(summarised), 3, "the other three must keep their summary")
        self.assertEqual(records[1]["summary"], "Feed summary 1",
                         "the refused story keeps the feed text")
        self.assertLessEqual(len(client.calls), 10, "splitting must terminate")

    def test_empty_response_is_split_too(self):
        """An empty body is a refusal, not a success."""
        records = self.records(4)
        records[2]["title"] = "poison headline the model will not repeat"
        engine = DigestEngine(self.config, self.now)
        engine.state["articles"] = {r["id"]: dict(r) for r in records}
        client = EmptyClient()

        with patch.object(engine, "_get_ai_client", return_value=client):
            engine._apply_ai_summaries(records)

        summarised = [r for r in records if r["summary"].startswith("中文简介")]
        self.assertEqual(len(summarised), 3)
        self.assertEqual(records[2]["summary"], "Feed summary 2")

    def test_missing_api_key_keeps_feed_summaries(self):
        records = self.records(3)
        engine = DigestEngine(self.config, self.now)
        engine.state["articles"] = {r["id"]: dict(r) for r in records}

        with patch.object(engine, "_get_ai_client", return_value=None):
            engine._apply_ai_summaries(records)

        for index, record in enumerate(records):
            self.assertEqual(record["summary"], f"Feed summary {index}")

    def test_disabled_feature_does_nothing(self):
        records = self.records(3)
        config = dict(self.config, AI_SUMMARIES={"ENABLED": False, "BATCH_SIZE": 4})
        engine = DigestEngine(config, self.now)
        client = RefusingClient()

        with patch.object(engine, "_get_ai_client", return_value=client):
            engine._apply_ai_summaries(records)

        self.assertEqual(client.calls, [])

    def test_prompt_uses_the_translated_text_when_available(self):
        """Summaries should be written from the Chinese text, not the English."""
        records = self.records(2)
        engine = DigestEngine(self.config, self.now)
        engine.state["articles"] = {r["id"]: dict(r) for r in records}
        engine.translation_cache["entries"] = {
            r["content_hash"]: {"title_zh": f"中文标题 {r['id']}", "summary_zh": f"中文摘要 {r['id']}"}
            for r in records
        }
        client = RefusingClient()

        with patch.object(engine, "_get_ai_client", return_value=client):
            engine._apply_ai_summaries(records)

        self.assertTrue(client.calls)
        self.assertIn("中文标题", client.calls[0])
        self.assertNotIn("Story number", client.calls[0])


if __name__ == "__main__":
    unittest.main()
