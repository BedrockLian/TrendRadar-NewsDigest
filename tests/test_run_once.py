"""Tests for serialized crawl and publication runs."""

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from deployment.run_once import run_once


class RunOnceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.public = self.root / "public"

    def tearDown(self):
        self.temp.cleanup()

    def test_serializes_the_crawl_and_publish_sequence(self):
        counter = {"active": 0, "maximum": 0, "runs": 0}
        counter_lock = threading.Lock()

        def fake_crawl(*_args, **_kwargs):
            self.assertEqual(_kwargs["env"]["TRENDRADAR_MANAGED_RUN"], "1")
            with counter_lock:
                counter["active"] += 1
                counter["maximum"] = max(counter["maximum"], counter["active"])
                counter["runs"] += 1
                run_number = counter["runs"]

            time.sleep(0.05)
            briefings = self.output / "briefings/2026-09"
            briefings.mkdir(parents=True, exist_ok=True)
            for existing in briefings.glob("*.md"):
                existing.unlink()
            (self.output / "index.html").write_text(
                str(run_number), encoding="utf-8"
            )
            (briefings / f"2026-09-10-0800-run-{run_number}.md").write_text(
                f"# run {run_number}\n", encoding="utf-8"
            )

            with counter_lock:
                counter["active"] -= 1
            return subprocess.CompletedProcess([], 0)

        with patch("deployment.run_once.subprocess.run", side_effect=fake_crawl):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda _: run_once(self.output, self.public), range(2)))

        winner = (self.public / "index.html").read_text(encoding="utf-8")
        self.assertEqual(counter["maximum"], 1)
        self.assertEqual(counter["runs"], 2)
        self.assertTrue(
            (
                self.public
                / f"briefings/2026-09/2026-09-10-0800-run-{winner}.md"
            ).is_file()
        )

    def test_does_not_publish_after_failed_crawl(self):
        self.output.mkdir()
        old_output = self.output / "index.html"
        old_output.write_text("old output", encoding="utf-8")
        self.public.mkdir()
        old_homepage = self.public / "index.html"
        old_homepage.write_text("old", encoding="utf-8")

        failure = subprocess.CalledProcessError(1, ["python", "-m", "trendradar"])
        with patch("deployment.run_once.subprocess.run", side_effect=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                run_once(self.output, self.public)

        self.assertEqual(old_homepage.read_text(encoding="utf-8"), "old")
        self.assertEqual(old_output.read_text(encoding="utf-8"), "old output")

    def test_rejects_success_without_a_fresh_homepage(self):
        self.output.mkdir()
        stale_output = self.output / "index.html"
        stale_output.write_text("stale output", encoding="utf-8")
        self.public.mkdir()
        live_homepage = self.public / "index.html"
        live_homepage.write_text("live", encoding="utf-8")

        with patch(
            "deployment.run_once.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0),
        ):
            with self.assertRaises(RuntimeError):
                run_once(self.output, self.public)

        self.assertEqual(stale_output.read_text(encoding="utf-8"), "stale output")
        self.assertEqual(live_homepage.read_text(encoding="utf-8"), "live")

    def test_cli_returns_nonzero_for_operational_failure(self):
        environment = dict(os.environ)
        environment["CONFIG_PATH"] = str(self.root / "missing-config.yaml")
        environment["PYTHONIOENCODING"] = "utf-8"

        completed = subprocess.run(
            [sys.executable, "-m", "trendradar"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("配置文件错误", completed.stdout)


if __name__ == "__main__":
    unittest.main()
