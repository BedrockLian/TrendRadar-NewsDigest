#!/usr/bin/env bash
# Switch only the verified news site's upstream, preserving all other sites.
set -euo pipefail
ROOT=/opt/trendradar-next
curl --fail --silent http://127.0.0.1:18081/health/ >/dev/null
systemctl stop trendradar-collect.timer
for i in $(seq 1 180); do
  STATE=$(systemctl is-active trendradar-collect.service || true)
  test "$STATE" != activating && test "$STATE" != active && break
  sleep 5
done
STATE=$(systemctl is-active trendradar-collect.service || true)
if test "$STATE" = activating || test "$STATE" = active; then echo 'Old collector still running'; exit 1; fi
bash "$ROOT/current/deploy/run.sh" import-legacy /opt/trendradar
PROXY=/www/server/panel/vhost/nginx/proxy/news.blian117.dpdns.org
test -d "$PROXY"
mkdir -p /etc/trendradar-next/proxy-backup
cp -a "$PROXY/." /etc/trendradar-next/proxy-backup/
python3 - "$PROXY" <<'PY'
import pathlib,sys
files=list(pathlib.Path(sys.argv[1]).glob('*.conf'))
matched=0
for file in files:
    text=file.read_text()
    if 'proxy_pass http://127.0.0.1:18080/' in text:
        text=text.replace('proxy_pass http://127.0.0.1:18080/;', 'proxy_pass http://127.0.0.1:18081/;\n    proxy_set_header X-Forwarded-Proto $scheme;\n    proxy_buffering off;\n    proxy_read_timeout 300s;')
        file.write_text(text);matched+=1
if matched!=1:raise SystemExit('Expected exactly one matching old upstream')
PY
if ! /www/server/nginx/sbin/nginx -t; then
  cp -a /etc/trendradar-next/proxy-backup/. "$PROXY/"
  systemctl start trendradar-collect.timer
  exit 1
fi
/www/server/nginx/sbin/nginx -s reload
systemctl enable --now trendradar-next-scheduler trendradar-next-collect trendradar-next-ai trendradar-next-maintenance
echo 'New application is serving the news domain. Old files are retained until verification and backup.'
