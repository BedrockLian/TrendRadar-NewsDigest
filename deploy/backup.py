"""Stream a remote backup to the workstation, verify its archive, then mark success."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("RADAR_BACKUP_HOST"))
    parser.add_argument("--directory", default=str(Path.home() / "Documents/Trendradar-backups"))
    parser.add_argument(
        "--pg-restore",
        default=str(Path(__file__).resolve().parents[1] / ".local/postgres/pgsql/bin/pg_restore.exe"),
    )
    args = parser.parse_args()
    if not args.host:
        parser.error("provide --host or set RADAR_BACKUP_HOST")
    folder = Path(args.directory).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    temporary = folder / f"{stamp}.partial"
    destination = folder / f"{stamp}.dump"
    try:
        with temporary.open("wb") as file:
            subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=20",
                    args.host,
                    "bash /opt/trendradar-next/current/deploy/backup.sh",
                ],
                stdout=file,
                check=True,
            )
        subprocess.run([args.pg_restore, "--list", str(temporary)], check=True, stdout=subprocess.DEVNULL)
        temporary.replace(destination)
        checksum = hashlib.file_digest(destination.open("rb"), "sha256").hexdigest()
        destination.with_suffix(".sha256").write_text(checksum + "\n", encoding="ascii")
        # Only completed verified archives are eligible for retention rotation.
        all_backups = sorted(folder.glob("*.dump"), reverse=True)
        keep = set(all_backups[:7])
        weeks = set()
        for path in all_backups:
            week = datetime.strptime(path.stem, "%Y%m%d-%H%M%S").replace(tzinfo=UTC).isocalendar()[:2]
            if week not in weeks and len(weeks) < 4:
                keep.add(path)
                weeks.add(week)
        for path in all_backups:
            if path not in keep:
                assert path.parent == folder
                path.unlink()
                path.with_suffix(".sha256").unlink(missing_ok=True)
        command = "bash /opt/trendradar-next/current/deploy/run.sh backup-complete"
        subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                args.host,
                command,
            ],
            check=True,
        )
        (folder / "last-result.json").write_text(
            json.dumps(
                {
                    "status": "ok",
                    "file": str(destination),
                    "bytes": destination.stat().st_size,
                    "sha256": checksum,
                }
            ),
            encoding="utf-8",
        )
        print(f"Verified backup: {destination.name} ({destination.stat().st_size} bytes)")
    except Exception as exc:
        (folder / "last-result.json").write_text(
            json.dumps({"status": "failed", "error": type(exc).__name__}), encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    main()
