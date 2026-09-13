#!/usr/bin/env bash
# Use only after explicit authorization, successful cutover and off-host backups.
set -euo pipefail
test "${1:-}" = '--verified-backup-and-cutover' || exit 2
TARGET=$(realpath /opt/trendradar)
test "$TARGET" = /opt/trendradar
test -f /opt/trendradar-next/current/uv.lock
test -f /etc/trendradar-next/legacy-backed-up
curl --fail --silent https://news.blian117.dpdns.org/health/ >/dev/null
systemctl disable --now trendradar-collect.timer trendradar-web.service
STATE=$(systemctl is-active trendradar-collect.service || true)
test "$STATE" != activating && test "$STATE" != active
rm -f /etc/systemd/system/trendradar-collect.service /etc/systemd/system/trendradar-collect.timer /etc/systemd/system/trendradar-web.service
systemctl daemon-reload
rm -rf -- "$TARGET"
echo 'Removed the old /opt/trendradar repository and its three service definitions.'
