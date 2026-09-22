import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(prog="radar")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("check")
    sub.add_parser("status")
    sub.add_parser("backup-complete")
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
    # Renaming the administrator must retire the previous login in the same step.
    admin.add_argument("--retire", action="append", default=[], metavar="USERNAME")
    sub.add_parser("maintain")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--ai", action="store_true")
    ai_backfill = sub.add_parser("ai-backfill")
    ai_backfill.add_argument("--scope", choices=["live", "imported", "all"], default="all")
    ai_backfill.add_argument("--limit", type=int, default=1000)
    event_auto = sub.add_parser("events-auto")
    event_auto.add_argument("--limit", type=int, default=24)
    event_auto.add_argument("--lookback-hours", type=int, default=24)
    event_auto.add_argument("--batches", type=int, default=1)
    event_auto.add_argument("--audit-now", action="store_true")
    bench = sub.add_parser("benchmark")
    bench.add_argument("--count", type=int, default=1000000)
    bench.add_argument("--confirm-test-database", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.settings")
    import django

    django.setup()
    from django.core.management import call_command
    from django.utils import timezone

    from .models import Job, SiteSettings

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

        password = Path(args.password_file).read_text(encoding="utf-8").strip()
        if len(password) < 12:
            raise ValueError("管理员密码至少12位")
        accounts = get_user_model().objects
        user, created = accounts.get_or_create(username=args.username)
        validate_password(password, user)
        user.set_password(password)
        user.is_staff = user.is_superuser = user.is_active = True
        user.save()
        retired = []
        for name in args.retire:
            if name == args.username:
                continue
            # A renamed administrator must not leave a working login behind.
            for old in accounts.filter(username=name):
                old.is_active = old.is_staff = old.is_superuser = False
                old.set_unusable_password()
                old.save()
                retired.append(old.username)
        print(f"管理员已{'创建' if created else '更新'}：{args.username}")
        if retired:
            print(f"已停用旧账号：{'、'.join(retired)}")
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
        SiteSettings.objects.filter(pk=1).update(last_backup=timezone.now())
        print("已记录备份完成时间")
    elif args.command == "benchmark":
        from .benchmark import run

        print(json.dumps(run(args.count, args.confirm_test_database), ensure_ascii=False, indent=2))
    elif args.command == "verify":
        from .verify import verify

        print(json.dumps(verify(args.ai), ensure_ascii=False, indent=2))
    elif args.command == "ai-backfill":
        from app.ai.services import queue_backfill

        print(json.dumps(queue_backfill(args.scope, args.limit), ensure_ascii=False, indent=2))
    elif args.command == "events-auto":
        from .tasks import enqueue

        job = enqueue(
            "event_discovery",
            f"manual-major-events:{timezone.now().timestamp()}",
            {
                "limit": args.limit,
                "lookback_hours": args.lookback_hours,
                "batches": args.batches,
                "audit_only": args.audit_now,
                "force": args.audit_now,
            },
            queue="ai",
            priority=5,
        )
        print(json.dumps({"job": str(job.pk)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
