"""Tests for publishing the generated site without exposing runtime state."""

import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from deployment.publish_static import publish_static


class PublishStaticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.public = self.root / "public"
        self.output.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative: str, content: str) -> Path:
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_publishes_homepage_and_generated_archive_reading_pages(self):
        self.write("index.html", "<!doctype html><title>Today</title>")
        self.write(
            "briefings/2026-09/2026-09-10-0800-morning_digest.md",
            "# 早间新闻简报\n\n> 生成时间：2026-09-10 08:00｜共 1 篇\n",
        )
        self.write("briefings/.state.json", '{"private": true}')
        self.write("briefings/raw.db", "private")
        self.write("rss/2026-09-10.db", "private")

        published = publish_static(self.output, self.public)

        self.assertEqual(published.read_text(encoding="utf-8"), "<!doctype html><title>Today</title>")
        archive = self.public / "briefings"
        self.assertTrue((archive / "index.html").is_file())
        self.assertTrue(
            (archive / "2026-09/2026-09-10-0800-morning_digest.md").is_file()
        )
        detail = archive / "2026-09/2026-09-10-0800-morning_digest.html"
        self.assertTrue(detail.is_file())
        self.assertIn("下载 Markdown", detail.read_text(encoding="utf-8"))
        self.assertFalse((archive / ".state.json").exists())
        self.assertFalse((archive / "raw.db").exists())
        self.assertFalse((self.public / "rss").exists())

    def test_replaces_stale_archive_files(self):
        self.write("index.html", "new")
        self.write(
            "briefings/2026-09/2026-09-10-1230-noon_digest.md",
            "# 午间新闻简报\n",
        )
        stale = self.public / "briefings/old.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("old", encoding="utf-8")
        leaked = self.public / "rss/private.db"
        leaked.parent.mkdir()
        leaked.write_text("private", encoding="utf-8")
        state = self.public / ".state.json"
        state.write_text("private", encoding="utf-8")

        publish_static(self.output, self.public)

        self.assertFalse(stale.exists())
        self.assertFalse(leaked.exists())
        self.assertFalse(state.exists())
        self.assertTrue(
            (self.public / "briefings/2026-09/2026-09-10-1230-noon_digest.md").exists()
        )

    def test_keeps_live_archive_when_index_build_fails(self):
        self.write("index.html", "new")
        live_index = self.public / "index.html"
        live_archive = self.public / "briefings/old.md"
        live_archive.parent.mkdir(parents=True)
        live_index.write_text("old homepage", encoding="utf-8")
        live_archive.write_text("old archive", encoding="utf-8")

        with patch("deployment.publish_static.build_index", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                publish_static(self.output, self.public)

        self.assertEqual(live_index.read_text(encoding="utf-8"), "old homepage")
        self.assertEqual(live_archive.read_text(encoding="utf-8"), "old archive")

    def test_rolls_back_whole_site_when_final_swap_fails(self):
        self.write("index.html", "new homepage")
        self.write("briefings/2026-09/new.md", "# new archive\n")
        live_index = self.public / "index.html"
        live_archive = self.public / "briefings/old.md"
        live_archive.parent.mkdir(parents=True)
        live_index.write_text("old homepage", encoding="utf-8")
        live_archive.write_text("old archive", encoding="utf-8")
        real_replace = os.replace

        def fail_staged_swap(source, destination):
            source_path = Path(source)
            if source_path.name.startswith(".public.next-"):
                raise OSError("simulated final swap failure")
            return real_replace(source, destination)

        with (
            patch("deployment.publish_static._exchange_directories", return_value=False),
            patch("deployment.publish_static.os.replace", side_effect=fail_staged_swap),
        ):
            with self.assertRaises(OSError):
                publish_static(self.output, self.public)

        self.assertEqual(live_index.read_text(encoding="utf-8"), "old homepage")
        self.assertEqual(live_archive.read_text(encoding="utf-8"), "old archive")
        self.assertFalse((self.public / "briefings/2026-09/new.md").exists())

    def test_serializes_concurrent_publications_and_keeps_versions_together(self):
        outputs = []
        for name in ("one", "two"):
            output = self.root / name
            briefings = output / "briefings/2026-09"
            briefings.mkdir(parents=True)
            (output / "index.html").write_text(name, encoding="utf-8")
            (briefings / f"2026-09-10-0800-{name}.md").write_text(
                f"# {name}\n", encoding="utf-8"
            )
            outputs.append(output)

        from deployment import publish_static as publisher

        original_build_index = publisher.build_index
        counter = {"active": 0, "maximum": 0}
        counter_lock = threading.Lock()

        def slow_build_index(path):
            with counter_lock:
                counter["active"] += 1
                counter["maximum"] = max(counter["maximum"], counter["active"])
            time.sleep(0.05)
            try:
                return original_build_index(path)
            finally:
                with counter_lock:
                    counter["active"] -= 1

        with patch.object(publisher, "build_index", side_effect=slow_build_index):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda output: publish_static(output, self.public), outputs))

        winner = (self.public / "index.html").read_text(encoding="utf-8")
        self.assertEqual(counter["maximum"], 1)
        self.assertIn(winner, {"one", "two"})
        self.assertTrue(
            (self.public / f"briefings/2026-09/2026-09-10-0800-{winner}.md").is_file()
        )
        loser = "two" if winner == "one" else "one"
        self.assertFalse(
            (self.public / f"briefings/2026-09/2026-09-10-0800-{loser}.md").exists()
        )

    def test_rejects_missing_or_empty_homepage(self):
        with self.assertRaises(FileNotFoundError):
            publish_static(self.output, self.public)
        self.write("index.html", "")
        with self.assertRaises(FileNotFoundError):
            publish_static(self.output, self.public)

    def test_rejects_filesystem_root_as_public_directory(self):
        self.write("index.html", "homepage")

        with self.assertRaises(ValueError):
            publish_static(self.output, Path(self.root.anchor))

    def test_rejects_output_and_public_directory_containment(self):
        self.write("index.html", "homepage")
        important = self.root / "important.txt"
        important.write_text("keep", encoding="utf-8")

        with self.assertRaises(ValueError):
            publish_static(self.output, self.root)
        with self.assertRaises(ValueError):
            publish_static(self.output, self.output / "public")

        self.assertEqual(important.read_text(encoding="utf-8"), "keep")
        self.assertTrue((self.output / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
