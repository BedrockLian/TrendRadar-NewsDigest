#!/bin/sh
set -eu

APP_DIR=/opt/trendradar
cd "$APP_DIR"

.venv/bin/python -m deployment.run_once output public
