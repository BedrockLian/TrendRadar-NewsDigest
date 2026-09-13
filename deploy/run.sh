#!/usr/bin/env bash
set -euo pipefail
set -a
. /etc/trendradar-next/app.env
set +a
cd /opt/trendradar-next/current
exec .venv/bin/radar "$@"
