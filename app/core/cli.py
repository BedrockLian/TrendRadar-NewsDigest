import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(prog="radar")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("check")
    sub.add_parser("status")
    backup = sub.add_parser("backup-complete")
    # The marker gates deletion of the legacy repository, so it is only written
    # when the caller has actually restored/listed the archive off the host.
    backup.add_argument("--verified-legacy-backup", action="store_true")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18081)
    worker = sub.add_parser("worker")
    worker.add_argument("queue", choices=["collect", "ai", "maintenance"])
    worker.add_argument("--once", action="store_true")
    schedule = sub.add_parser("scheduler")
    schedule.add_argument("--once", action="store_true")
    collect = sub.add_parser("collect")
    collect.add_argument("--feed", type=int)
    brief = sub.add_parser("brief")
    brief.add_argument("--end")
    imp = sub.add_parser("import-legacy")
    imp.add_argument("root")
    imp.add_argument("--dry-run", action="store_true")
    imp.add_argument("--max-articles", type=int)
    admin = sub.add_parser("admin")
    admin.add_argument("--username", default="admin")
    admin.add_argument("--password-file", required=True)
    sub.add_parser("maintain")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--ai", action="store_true")
    bench = sub.add_parser("benchmark")
    bench.add_argument("--count", type=int, default=1000000)
    bench.add_argument("--confirm-test-database", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.settings")
    import django

    django.setup()
    from django.core.management import call_command
    from django.utils import timezone
    from .models import SiteSettings, Job

    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "app.core.asgi:application",
            host=args.host,
            port=args.port,
            proxy_headers=True,
            forwarded_allow_ips="127.0.0.1",
        )
    elif args.command == "migrate":
        call_command("migrate", interactive=False)
        SiteSettings.current()
    elif args.command == "check":
        call_command("check", deploy=True)
    elif args.command == "worker":
        from .tasks import worker

        worker(args.queue, args.once)
    elif args.command == "scheduler":
        from .tasks import scheduler

        scheduler(args.once)
    elif args.command == "collect":
        import uuid
        from app.news.models import Feed
        from .tasks import enqueue

        rows = Feed.objects.filter(enabled=True)
        if args.feed:
            rows = rows.filter(pk=args.feed)
        for f in rows:
            enqueue("collect", f"manual:{f.pk}:{uuid.uuid4()}", {"feed": f.pk}, queue="collect")
        print(json.dumps({"queued": rows.count()}))
    elif args.command == "brief":
        from app.briefs.services import generate

        print(generate(end=args.end).pk)
    elif args.command == "import-legacy":
        from app.news.importer import import_legacy

        print(
            json.dumps(
                import_legacy(args.root, args.dry_run, args.max_articles), ensure_ascii=False, indent=2
            )
        )
    elif args.command == "admin":
        from pathlib import Path
        from django.contrib.auth import get_user_model
        from django.contrib.auth.password_validation import validate_password

        password = Path(args.password_file).read_text().strip()
        if len(password) < 16:
            raise ValueError("管理员密码至少16位")
        user, _ = get_user_model().objects.get_or_create(username=args.username)
        validate_password(password, user)
        user.set_password(password)
        user.is_staff = user.is_superuser = True
        user.save()
        print("管理员已设置")
    elif args.command == "maintain":
        from .storage import maintain

        print(json.dumps(maintain(), ensure_ascii=False))
    elif args.command == "status":
        from .storage import measure

        print(
            json.dumps(
                {"storage": measure(), "pending": Job.objects.filter(status="pending").count()},
                ensure_ascii=False,
            )
        )
    elif args.command == "backup-complete":
        from pathlib import Path

        SiteSettings.objects.filter(pk=1).update(last_backup=timezone.now())
        if args.verified_legacy_backup:
            marker = Path("/etc/trendradar-next/legacy-backed-up")
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(f"{timezone.now().isoformat()}\n", encoding="utf-8")
            print("已记录离机备份标记")
    elif args.command == "benchmark":
        from .benchmark import run

        print(json.dumps(run(args.count, args.confirm_test_database), ensure_ascii=False, indent=2))
    elif args.command == "verify":
        from .verify import verify

        print(json.dumps(verify(args.ai), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
