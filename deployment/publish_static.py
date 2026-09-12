"""Publish the safe, public subset of TrendRadar's generated output."""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

from trendradar.report.archive import build_index
from trendradar.report.html import SUMMARIES_FILENAME

from deployment.compress import compress_tree


def _resolved_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.parent == resolved:
        raise ValueError(f"refusing to publish into a filesystem root: {resolved}")
    return resolved


def _copy_markdown_archive(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return

    for source_file in source.rglob("*.md"):
        if not source_file.is_file() or source_file.is_symlink():
            continue
        relative = source_file.relative_to(source)
        destination_file = destination / relative
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination_file)


def _try_lock(handle: BinaryIO) -> bool:
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, OSError):
        return False


def _unlock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def exclusive_lock(lock_path: Path, timeout: float = 60.0) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        deadline = time.monotonic() + timeout
        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for publication lock: {lock_path}")
            time.sleep(0.1)

        try:
            yield
        finally:
            _unlock(handle)


def _exchange_directories(left: Path, right: Path) -> bool:
    """Atomically exchange two directories when Linux renameat2 is available."""

    if os.name != "posix":
        return False

    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        return False

    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(-100, os.fsencode(left), -100, os.fsencode(right), 2)
    if result == 0:
        return True

    error = ctypes.get_errno()
    unsupported = {
        errno.EINVAL,
        errno.ENOSYS,
        errno.EXDEV,
        getattr(errno, "EOPNOTSUPP", errno.EINVAL),
    }
    if error in unsupported:
        return False
    raise OSError(error, os.strerror(error), f"{left} <-> {right}")


def _replace_directory(staged: Path, live: Path, backup: Path) -> None:
    shutil.rmtree(backup, ignore_errors=True)
    if live.exists() and _exchange_directories(staged, live):
        # ``staged`` now names the previous live tree; cleanup can happen later
        # without creating a gap at the public path.
        shutil.rmtree(staged, ignore_errors=True)
        return

    moved_live = False
    try:
        if live.exists():
            os.replace(live, backup)
            moved_live = True
        os.replace(staged, live)
    except Exception:
        if moved_live and backup.exists() and not live.exists():
            os.replace(backup, live)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


def publish_static(output_dir: Path, public_dir: Path) -> Path:
    """Publish the homepage plus Markdown briefings and derived HTML readers.

    Runtime databases, alert state, crawl snapshots, and other internal files stay
    in ``output_dir`` and are never copied into the served directory.
    """

    output = output_dir.expanduser().resolve()
    public = _resolved_directory(public_dir)
    if (
        output == public
        or output.is_relative_to(public)
        or public.is_relative_to(output)
    ):
        raise ValueError("output and public directories must be separate, disjoint trees")

    source_index = output / "index.html"
    if not source_index.is_file() or source_index.stat().st_size == 0:
        raise FileNotFoundError(f"generated homepage is missing or empty: {source_index}")

    public.parent.mkdir(parents=True, exist_ok=True)
    lock_path = public.parent / f".{public.name}.publish.lock"

    with exclusive_lock(lock_path):
        staged = Path(
            tempfile.mkdtemp(prefix=f".{public.name}.next-", dir=public.parent)
        )
        backup = public.parent / f".{public.name}.previous-{uuid.uuid4().hex}"
        try:
            staged_archive = staged / "briefings"
            staged_archive.mkdir()
            _copy_markdown_archive(output / "briefings", staged_archive)
            build_index(staged_archive)
            shutil.copy2(source_index, staged / "index.html")

            # The readings page (运行概览) sits one directory down; the sidebar
            # links to it from every page, so it ships with the homepage or the
            # link 404s.  The generator writes it in the same run as the
            # homepage, from the same snapshot.
            source_overview = output / "overview" / "index.html"
            if source_overview.is_file() and not source_overview.is_symlink():
                staged_overview = staged / "overview"
                staged_overview.mkdir()
                shutil.copy2(source_overview, staged_overview / "index.html")

            # Optional sibling data file holding the article summaries the
            # homepage payload omits.  Whitelisted by exact name only.
            source_summaries = output / SUMMARIES_FILENAME
            if source_summaries.is_file() and not source_summaries.is_symlink():
                shutil.copy2(source_summaries, staged / SUMMARIES_FILENAME)

            # Precompress every text asset once, here, so the origin never has
            # to gzip the homepage per request.  ``.gz`` sidecars are derived
            # artifacts of files that are already public, so the whitelist of
            # *sources* is unchanged.
            compress_tree(staged)

            _replace_directory(staged, public, backup)
        finally:
            shutil.rmtree(staged, ignore_errors=True)

    return public / "index.html"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m deployment.publish_static OUTPUT_DIR PUBLIC_DIR")
    published = publish_static(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Published static site: {published}")


if __name__ == "__main__":
    main()
