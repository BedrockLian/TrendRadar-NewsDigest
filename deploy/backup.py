"""Stream a remote backup to the workstation, verify its archive, then mark success."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="campus-server")
    parser.add_argument("--directory", default=str(Path.home() / "Documents/Trendradar-backups"))
    parser.add_argument(
        "--pg-restore",
        default=str(Path(__file__).resolve().parents[1] / ".local/postgres/pgsql/bin/pg_restore.exe"),
    )
    parser.add_argument(
        "--mark-legacy-backed-up",
        action="store_true",
        help="同时记录离机备份标记，解锁旧仓库清理（仅在本次归档已验证后使用）",
    )
    args = parser.parse_args()
    folder = Path(args.directory).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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
            week = datetime.strptime(path.stem, "%Y%m%d-%H%M%S").isocalendar()[:2]
            if week not in weeks and len(weeks) < 4:
                keep.add(path)
                weeks.add(week)
        for path in all_backups:
            if path not in keep:
                assert path.parent == folder
                path.unlink()
                path.with_suffix(".sha256").unlink(missing_ok=True)
        command = "bash /opt/trendradar-next/current/deploy/run.sh backup-complete"
        if args.mark_legacy_backed_up:
            # Records that an off-host archive of the pre-cutover data exists;
            # remove-legacy.sh refuses to delete anything without this marker.
            command += " --verified-legacy-backup"
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
