# coding=utf-8
"""Deterministic gzip sidecar generation for the published static site.

The public site is served through a plain Python static server, so it cannot rely
on Nginx ``gzip_static``.  Instead the publisher writes a sibling ``<name>.gz``
next to every text asset and the server prefers that file when the client sends
``Accept-Encoding: gzip``.  Compressing once at publish time replaces compressing
the whole homepage on every single request.
"""

from __future__ import annotations

import gzip
import os
from pathlib import Path

# Files larger than this are skipped: the homepage is ~530 KB and compresses
# well, but anything far bigger is a sign of an unexpected artifact.
MAX_COMPRESS_BYTES = 32 * 1024 * 1024

# Suffixes that are worth compressing.  Databases, images, and the lock files
# never reach ``public`` but listing suffixes explicitly keeps the intent clear.
COMPRESSIBLE_SUFFIXES = frozenset({".html", ".htm", ".md", ".txt", ".css", ".js", ".json"})

GZIP_SUFFIX = ".gz"


def is_compressible(path: Path) -> bool:
    """Return True when ``path`` is a text asset the publisher should compress."""

    return path.suffix.lower() in COMPRESSIBLE_SUFFIXES


def compress_file(source: Path) -> Path | None:
    """Write ``<source>.gz`` and return it, or ``None`` when nothing was written.

    The gzip header stores no filename, no timestamp, and a fixed compression
    level so repeated publishes of identical input produce byte-identical
    output.  That keeps the published tree reproducible and diff-friendly.
    """

    if not source.is_file() or source.is_symlink():
        return None
    if not is_compressible(source):
        return None

    size = source.stat().st_size
    if size == 0 or size > MAX_COMPRESS_BYTES:
        return None

    raw = source.read_bytes()
    target = source.with_name(source.name + GZIP_SUFFIX)

    with target.open("wb") as handle:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=handle,
            compresslevel=9,
            mtime=0,
        ) as gz:
            gz.write(raw)

    # Align the sidecar's mtime with its source (whole seconds only: the step
    # resolution of ``os.utime`` differs per platform) so a single
    # ``If-Modified-Since`` check stays valid for both representations.
    stat = source.stat()
    os.utime(target, (int(stat.st_atime), int(stat.st_mtime)))
    return target


def compress_tree(root: Path) -> int:
    """Compress every eligible file under ``root``; return how many were written."""

    if not root.is_dir():
        return 0

    written = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name.endswith(GZIP_SUFFIX):
            continue
        if compress_file(path) is not None:
            written += 1
    return written
