"""Focused RSS curation regressions; run with unittest discovery."""
import unittest
from pathlib import Path

import yaml

from trendradar.core.analyzer import count_rss_frequency, group_rss_stats_by_source


def article(title, url, source="A", published="2026-09-08T08:00:00+00:00"):
    return {"title": title, "url": url, "feed_name": source, "published_at": published}


class CuratedRSSTest(unittest.TestCase):
    def analyze(self, items, **kwargs):
        return count_rss_frequency(items, [], [], quiet=True, **kwargs)[0]

    def test_tracking_urls_and_exact_title_copies_are_deduplicated(self):
        items = [
            article("Iran investigation", "https://example.org/article/?id=1&utm_source=rss#top"),
            article("Alternate syndicated headline", "https://example.org/article?gclid=y&id=1&fbclid=x", "B"),
            article(" IRAN  investigation ", "https://other.org/copy", "C"),
            article("Iran diplomacy analysis", "https://example.org/article?id=2", "B"),
        ]
        stats = self.analyze(items)
        self.assertEqual(stats[0]["count"], 2)
        self.assertEqual([t["title"] for t in stats[0]["titles"]],
                         ["Iran investigation", "Iran diplomacy analysis"])

    def test_source_groups_sort_by_publication_time(self):
        items = [article("Earlier", "https://a/1"),
                 article("Other publisher", "https://b/1", "B"),
                 article("Later", "https://a/2", published="2026-09-08T10:00:00+00:00")]
        groups = group_rss_stats_by_source(self.analyze(items))
        by_source = {group["word"]: group for group in groups}
        self.assertEqual(set(by_source), {"A", "B"})
        self.assertEqual([t["title"] for t in by_source["A"]["titles"]], ["Later", "Earlier"])
        self.assertEqual(by_source["A"]["count"], 2)
        self.assertEqual(group_rss_stats_by_source([]), [])

    def test_tracking_variant_still_marked_new(self):
        items = [article("New article", "https://a/1?utm_source=feed")]
        stats = self.analyze(items, new_items=[article("New article", "https://a/1")])
        self.assertTrue(stats[0]["titles"][0]["is_new"])

    def test_technology_canary_feeds_are_configured_and_categorised(self):
        config = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
        feeds = {feed["id"]: feed for feed in config["rss"]["feeds"]}
        expected = {
            "techcrunch": "https://techcrunch.com/feed/",
            "the-verge": "https://www.theverge.com/rss/index.xml",
            "engadget": "https://www.engadget.com/rss.xml",
        }
        self.assertEqual({key: feeds[key]["url"] for key in expected}, expected)

        category = next(item for item in config["digest"]["categories"] if item["id"] == "tech_ai")
        self.assertTrue(set(expected).issubset(category["feeds"]))
        self.assertTrue(set(category["feeds"]).issubset(feeds))


if __name__ == "__main__":
    unittest.main()
