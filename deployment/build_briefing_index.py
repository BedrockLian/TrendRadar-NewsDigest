"""Compatibility CLI for building the public briefing archive index."""

from trendradar.report.archive import ArchiveEntry, build_index, collect_entries, main

__all__ = ["ArchiveEntry", "build_index", "collect_entries", "main"]


if __name__ == "__main__":
    main()
