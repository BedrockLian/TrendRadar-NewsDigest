#!/usr/bin/env bash
# Install an isolated deployment; the existing site's proxy is not switched here.
set -euo pipefail
SOURCE=$(realpath "${1:?Usage: install.sh SOURCE_DIRECTORY}")
ROOT=/opt/trendradar-next
: "${RADAR_PUBLIC_HOST:?Set RADAR_PUBLIC_HOST to the HTTPS hostname before installation}"
test "$(id -u)" = 0 || { echo 'Run as root'; exit 1; }
test -f "$SOURCE/uv.lock"
. /etc/os-release
mkdir -p "$ROOT" /etc/trendradar-next /var/lib/trendradar-next /var/cache/trendradar-next
case "$ID" in
  opencloudos)
    PG_BIN="$ROOT/postgres18/bin"
    PG_DATA=/var/lib/trendradar-postgres
    PG_SERVICE=trendradar-postgres
    if ! test -x "$PG_BIN/postgres"; then
      dnf -y install gcc make zlib-devel openssl-devel libicu-devel bison flex pkgconf-pkg-config
      BUILD=$(mktemp -d /var/tmp/trendradar-pg.XXXXXX)
      curl --fail --location https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2 -o "$BUILD/source.tar.bz2"
      curl --fail --location https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2.sha256 -o "$BUILD/source.sha256"
      EXPECTED=$(awk '{print $1}' "$BUILD/source.sha256")
      echo "$EXPECTED  $BUILD/source.tar.bz2" | sha256sum --check
      tar -xjf "$BUILD/source.tar.bz2" -C "$BUILD"
      (cd "$BUILD/postgresql-18.6" && ./configure --prefix="$ROOT/postgres18" --with-openssl --without-readline && make -j2 && make install)
      rm -rf -- "$BUILD"
    fi
    id postgres >/dev/null 2>&1 || useradd --system --home-dir "$PG_DATA" --shell /sbin/nologin postgres
    install -d -o postgres -g postgres -m 700 "$PG_DATA"
    test -f "$PG_DATA/PG_VERSION" || runuser -u postgres -- "$PG_BIN/initdb" -D "$PG_DATA" --encoding=UTF8 --locale=C.UTF-8 --auth-local=peer --auth-host=scram-sha-256
    cat >"/etc/systemd/system/$PG_SERVICE.service" <<PGUNIT
[Unit]
Description=PostgreSQL 18 for Trendradar
After=network.target
[Service]
User=postgres
Group=postgres
ExecStart=$PG_BIN/postgres -D $PG_DATA
ExecReload=/bin/kill -HUP \$MAINPID
KillSignal=SIGINT
TimeoutStopSec=120
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=false
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PG_DATA /tmp
[Install]
WantedBy=multi-user.target
PGUNIT
    systemctl daemon-reload
    ;;
  rocky|almalinux|rhel|centos)
    cat >/etc/yum.repos.d/trendradar-pg18.repo <<'REPO'
[trendradar-pg18]
name=PostgreSQL 18 official
baseurl=https://download.postgresql.org/pub/repos/yum/18/redhat/rhel-9-x86_64
enabled=0
gpgcheck=1
gpgkey=https://download.postgresql.org/pub/repos/yum/keys/PGDG-RPM-GPG-KEY-RHEL
[trendradar-pg-common]
name=PostgreSQL common official
baseurl=https://download.postgresql.org/pub/repos/yum/common/redhat/rhel-9-x86_64
enabled=0
gpgcheck=1
gpgkey=https://download.postgresql.org/pub/repos/yum/keys/PGDG-RPM-GPG-KEY-RHEL
REPO
    dnf -y --enablerepo=trendradar-pg18,trendradar-pg-common install postgresql18-server postgresql18-contrib
    PG_BIN=/usr/pgsql-18/bin
    PG_DATA=/var/lib/pgsql/18/data
    PG_SERVICE=postgresql-18
    test -f "$PG_DATA/PG_VERSION" || "$PG_BIN/postgresql-18-setup" initdb
    ;;
  ubuntu|debian)
    apt-get update
    apt-get install -y curl ca-certificates postgresql-common
    /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
    apt-get install -y postgresql-18
    PG_BIN=/usr/lib/postgresql/18/bin
    PG_DATA=/var/lib/postgresql/18/main
    PG_SERVICE=postgresql
    ;;
  *) echo "Unsupported operating system: $ID"; exit 1;;
esac
systemctl enable --now "$PG_SERVICE"
id radar >/dev/null 2>&1 || useradd --system --home-dir /var/lib/trendradar-next --shell /sbin/nologin radar
if ! test -x "$ROOT/bin/uv"; then
    curl --fail --location https://astral.sh/uv/install.sh -o "$ROOT/uv-install.sh"
    UV_INSTALL_DIR="$ROOT/bin" sh "$ROOT/uv-install.sh"
fi
export UV_PYTHON_INSTALL_DIR="$ROOT/python" UV_CACHE_DIR=/var/cache/trendradar-next
"$ROOT/bin/uv" python install 3.14
cd "$SOURCE"
"$ROOT/bin/uv" sync --frozen --no-dev --python 3.14
# Secrets are generated or reused on the server, never printed or committed.
PG_BIN="$PG_BIN" RADAR_PUBLIC_HOST="$RADAR_PUBLIC_HOST" \
  RADAR_PUBLIC_ORIGIN="${RADAR_PUBLIC_ORIGIN:-https://$RADAR_PUBLIC_HOST}" \
  "$SOURCE/.venv/bin/python" "$SOURCE/deploy/provision.py"
systemctl restart "$PG_SERVICE"
ENV=/etc/trendradar-next/app.env
chmod 640 "$ENV"
chown root:radar "$ENV"
chown -R radar:radar /var/lib/trendradar-next
chmod 750 /var/lib/trendradar-next
set -a
. "$ENV"
set +a
export RADAR_STATIC_ROOT="$SOURCE/.local/static"
"$SOURCE/.venv/bin/radar" migrate
"$SOURCE/.venv/bin/python" -m django collectstatic --noinput
"$SOURCE/.venv/bin/radar" admin --password-file /etc/trendradar-next/admin-password
ln -sfn "$SOURCE" "$ROOT/current"
for unit in web scheduler collect ai maintenance; do
    case "$unit" in
      web) COMMAND='serve --port 18081'; MEMORY=240M;;
      scheduler) COMMAND='scheduler'; MEMORY=160M;;
      collect) COMMAND='worker collect'; MEMORY=300M;;
      ai) COMMAND='worker ai'; MEMORY=300M;;
      maintenance) COMMAND='worker maintenance'; MEMORY=300M;;
    esac
    cat >"/etc/systemd/system/trendradar-next-$unit.service" <<UNIT
[Unit]
Description=Trendradar $unit
After=network-online.target $PG_SERVICE.service
Wants=network-online.target
[Service]
User=radar
Group=radar
WorkingDirectory=$ROOT/current
EnvironmentFile=/etc/trendradar-next/app.env
ExecStart=$ROOT/current/.venv/bin/radar $COMMAND
Restart=on-failure
RestartSec=5
TimeoutStopSec=90
MemoryMax=$MEMORY
CPUQuota=50%
Nice=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/trendradar-next
[Install]
WantedBy=multi-user.target
UNIT
done
systemctl daemon-reload
# Start only the web service. Enable workers after migration and verification.
systemctl enable --now trendradar-next-web
echo 'Isolated web service ready at 127.0.0.1:18081; workers are not enabled yet.'
