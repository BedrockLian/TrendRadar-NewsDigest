"""Build a small public index for the Markdown briefing archive."""

from __future__ import annotations

import html
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    root = Path(sys.argv[1])
    files = sorted(root.rglob("*.md"), reverse=True)
    rows = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        label = relative.removesuffix(".md")
        rows.append(
            f'<li><a href="{html.escape(relative, quote=True)}">'
            f"{html.escape(label)}</a></li>"
        )

    listing = "\n".join(rows) if rows else "<li>暂无简报</li>"
    updated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>新闻简报存档</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ max-width: 760px; margin: 0 auto; padding: 32px 20px; line-height: 1.6; }}
    h1 {{ font-size: 1.6rem; margin: 0 0 4px; }}
    p {{ color: #777; margin: 0 0 24px; }}
    ul {{ padding-left: 1.25rem; }}
    li {{ margin: 8px 0; }}
    a {{ color: #2563eb; text-underline-offset: 3px; }}
  </style>
</head>
<body>
  <h1>新闻简报存档</h1>
  <p>最近更新：{html.escape(updated)}</p>
  <ul>{listing}</ul>
</body>
</html>
"""
    (root / "index.html").write_text(document, encoding="utf-8")


if __name__ == "__main__":
    main()
