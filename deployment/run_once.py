"""Run one serialized crawl and publish its complete static result."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

from deployment.publish_static import exclusive_lock, publish_static


def run_once(output_dir: Path, public_dir: Path) -> Path:
    output = output_dir.expanduser().resolve()
    public = public_dir.expanduser().resolve()
    run_lock = output.parent / f".{output.name}.run.lock"

    with exclusive_lock(run_lock):
        output.mkdir(parents=True, exist_ok=True)
        homepage = output / "index.html"
        previous_homepage = output / f".index.html.before-run-{uuid.uuid4().hex}"
        had_previous = homepage.is_file()
        if had_previous:
            homepage.replace(previous_homepage)

        try:
            environment = dict(os.environ)
            environment["TRENDRADAR_MANAGED_RUN"] = "1"
            subprocess.run(
                [sys.executable, "-m", "trendradar"],
                check=True,
                env=environment,
            )
            if not homepage.is_file() or homepage.stat().st_size == 0:
                raise RuntimeError("crawl completed without a new non-empty output/index.html")
        except Exception:
            if homepage.exists():
                homepage.unlink()
            if had_previous and previous_homepage.exists():
                previous_homepage.replace(homepage)
            raise
        else:
            if previous_homepage.exists():
                previous_homepage.unlink()
        return publish_static(output, public)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m deployment.run_once OUTPUT_DIR PUBLIC_DIR")
    published = run_once(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Crawl and publication complete: {published}")


if __name__ == "__main__":
    main()
