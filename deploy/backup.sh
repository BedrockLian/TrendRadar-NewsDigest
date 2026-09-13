#!/usr/bin/env bash
set -euo pipefail
for candidate in /opt/trendradar-next/postgres18/bin /usr/pgsql-18/bin /usr/lib/postgresql/18/bin; do
  if test -x "$candidate/pg_dump"; then
    exec runuser -u postgres -- "$candidate/pg_dump" --format=custom --compress=6 --no-owner --no-acl radar
  fi
done
echo 'PostgreSQL 18 tools unavailable' >&2
exit 1
