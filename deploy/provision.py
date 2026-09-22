"""Configure a dedicated database without exposing credentials in process output."""

import os
import secrets
import shlex
import subprocess
from pathlib import Path
from urllib.parse import quote

pg = Path(os.environ["PG_BIN"])
env = Path("/etc/trendradar-next/app.env")
if not env.exists():
    password = secrets.token_urlsafe(32)
    role_sql = f"CREATE ROLE radar LOGIN PASSWORD '{password}';"
    exists = subprocess.check_output(
        [
            "runuser",
            "-u",
            "postgres",
            "--",
            str(pg / "psql"),
            "-Atc",
            "SELECT 1 FROM pg_roles WHERE rolname='radar'",
        ]
    )
    if exists.strip():
        raise RuntimeError(
            "Role radar already exists without application configuration; refusing to replace password"
        )
    subprocess.run(
        ["runuser", "-u", "postgres", "--", str(pg / "psql"), "-v", "ON_ERROR_STOP=1"],
        input=role_sql.encode(),
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        ["runuser", "-u", "postgres", "--", str(pg / "createdb"), "-O", "radar", "radar"], check=True
    )
    public_host = os.environ["RADAR_PUBLIC_HOST"].strip()
    public_origin = os.environ.get("RADAR_PUBLIC_ORIGIN", f"https://{public_host}").strip()
    if not public_host or "://" in public_host or "/" in public_host:
        raise RuntimeError("RADAR_PUBLIC_HOST must be a hostname without a scheme or path")
    if not public_origin.startswith(("https://", "http://")):
        raise RuntimeError("RADAR_PUBLIC_ORIGIN must be an HTTP(S) origin")
    values = {
        "DJANGO_SETTINGS_MODULE": "app.core.settings",
        "RADAR_DEBUG": "0",
        "RADAR_SECRET_KEY": secrets.token_urlsafe(48),
        "DATABASE_URL": f"postgresql://radar:{quote(password)}@127.0.0.1:5432/radar",
        "RADAR_HOSTS": f"{public_host},localhost,127.0.0.1",
        "RADAR_ORIGINS": public_origin,
        "RADAR_DATA_PATH": "/var/lib/trendradar-next",
        "RADAR_DB_POOL": "3",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "DEEPSEEK_API_KEY": "",
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
    }
    env.write_text("\n".join(f"{k}={shlex.quote(v)}" for k, v in values.items()) + "\n")
    env.chmod(0o640)
admin = Path("/etc/trendradar-next/admin-password")
if not admin.exists():
    admin.write_text(secrets.token_urlsafe(24))
    admin.chmod(0o600)
# Cluster settings apply only to the new PostgreSQL installation.
sql = """ALTER SYSTEM SET listen_addresses='127.0.0.1';
ALTER SYSTEM SET shared_buffers='128MB';
ALTER SYSTEM SET work_mem='2MB';
ALTER SYSTEM SET maintenance_work_mem='64MB';
ALTER SYSTEM SET max_connections='30';
ALTER SYSTEM SET max_wal_size='1GB';
ALTER SYSTEM SET min_wal_size='80MB';
ALTER SYSTEM SET temp_file_limit='128MB';
ALTER SYSTEM SET log_rotation_age='1d';
ALTER SYSTEM SET log_truncate_on_rotation='on';
ALTER SYSTEM SET log_filename='postgresql-%a.log';
ALTER SYSTEM SET autovacuum_vacuum_scale_factor='0.05';
SELECT pg_reload_conf();
"""
subprocess.run(
    ["runuser", "-u", "postgres", "--", str(pg / "psql"), "-v", "ON_ERROR_STOP=1"],
    input=sql.encode(),
    check=True,
    stdout=subprocess.DEVNULL,
)
