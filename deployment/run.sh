#!/bin/sh
set -eu

APP_DIR=/opt/trendradar
cd "$APP_DIR"

.venv/bin/python -m trendradar

test -s output/index.html
install -m 644 output/index.html public/index.html.new
mv public/index.html.new public/index.html

# 只发布 Markdown 简报；内部去重状态 .state.json 不进入网页目录。
rm -rf public/briefings.next
mkdir -p public/briefings.next
if [ -d output/briefings ]; then
  (
    cd output/briefings
    find . -type f -name '*.md' -exec cp --parents '{}' "$APP_DIR/public/briefings.next/" \;
  )
fi
.venv/bin/python deployment/build_briefing_index.py public/briefings.next

rm -rf public/briefings.previous
if [ -d public/briefings ]; then
  mv public/briefings public/briefings.previous
fi
mv public/briefings.next public/briefings
rm -rf public/briefings.previous
