import shutil
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from app.ai.models import Conversation, Generation
from app.events.models import Candidate, Node
from app.news.models import Article, ArticleVersion, CrawlRun, FeedIdentity, Tombstone
from app.news.services import digest

from .models import Job, SiteSettings

GB = 1024**3


def measure():
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    # Production DATA_PATH must share the PostgreSQL data filesystem.
    free = shutil.disk_usage(settings.DATA_PATH).free
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        db = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COALESCE(sum(n_live_tup),0), COALESCE(sum(n_dead_tup),0) FROM pg_stat_user_tables"
        )
        live, dead = cursor.fetchone()
    return {
        "free_gb": round(free / GB, 3),
        "database_gb": round(db / GB, 3),
        "live_rows_estimate": int(live),
        "dead_rows_estimate": int(dead),
    }


def protected_articles():
    return Article.objects.filter(
        Q(versions__brief_items__isnull=False)
        | Q(versions__event_reports__node__confirmed=True)
        | Q(versions__favourite__isnull=False)
        | Q(job__status__in=["pending", "running"])
    )


def maintain():
    from app.news.partitions import ensure_partitions

    ensure_partitions()
    now = timezone.now()
    from .models import LoginAttempt

    LoginAttempt.objects.filter(since__lt=now - timedelta(days=1)).delete()
    config = SiteSettings.current()
    stats = measure()
    pressure = stats["free_gb"] < config.soft_free_gb or stats["database_gb"] >= config.db_budget_gb
    # Drop expired drafts before deleting versions; unconfirmed AI suggestions are not permanent pins.
    Node.objects.filter(confirmed=False, created_at__lt=now - timedelta(days=7)).delete()
    Candidate.objects.filter(status="pending", created_at__lt=now - timedelta(days=30)).delete()
    Job.objects.filter(status__in=["completed", "failed"], created_at__lt=now - timedelta(days=14)).delete()
    Tombstone.objects.filter(expires_at__lt=now).delete()
    Generation.objects.filter(version__isnull=True, created_at__lt=now - timedelta(days=30)).delete()
    Conversation.objects.filter(created_at__lt=now - timedelta(days=90)).delete()
    CrawlRun.objects.filter(created_at__lt=now - timedelta(days=14)).delete()
    cutoff = now - timedelta(hours=72) if pressure else now - timedelta(days=config.retention_days)
    removed = 0
    for _ in range(10):
        with transaction.atomic():
            rows = list(
                Article.objects.select_for_update(skip_locked=True)
                .filter(first_seen__lt=cutoff)
                .exclude(pk__in=protected_articles().values("pk"))
                .order_by("first_seen", "id")[:200]
            )
            if not rows:
                break
            ids = [a.pk for a in rows]
            # Locking rows is coordinated with commands that create permanent references.
            safe_ids = list(
                Article.objects.filter(pk__in=ids)
                .exclude(pk__in=protected_articles().values("pk"))
                .values_list("pk", flat=True)
            )
            keys = [a.url_hash for a in rows if a.pk in safe_ids]
            keys.extend(
                digest(f"{f}:{i}")
                for f, i in FeedIdentity.objects.filter(article_id__in=safe_ids).values_list(
                    "feed_id", "identity"
                )
            )
            Tombstone.objects.bulk_create(
                [Tombstone(key=k, expires_at=now + timedelta(days=30)) for k in set(keys)],
                ignore_conflicts=True,
            )
            from app.events.models import NodeReport

            NodeReport.objects.filter(node__confirmed=False, version__article_id__in=safe_ids).delete()
            Article.objects.filter(pk__in=safe_ids).update(current=None)
            Article.objects.filter(pk__in=safe_ids).delete()
            removed += len(safe_ids)
        if len(rows) < 200:
            break
    old = ArticleVersion.objects.filter(
        created_at__lt=now - timedelta(days=30),
        current_for__isnull=True,
        brief_items__isnull=True,
        event_reports__isnull=True,
        favourite__isnull=True,
    )
    old.exclude(article__job__status__in=["pending", "running"]).filter(
        pk__in=list(old.values_list("pk", flat=True)[:1000])
    ).delete()
    current = measure()
    current.update(
        {
            "checked_at": now.isoformat(),
            "removed": removed,
            "pressure": pressure,
            "backup_stale": not config.last_backup or config.last_backup < now - timedelta(hours=48),
        }
    )
    from django.db.models import Sum

    from app.news.models import HourStat

    daily = HourStat.objects.filter(hour__gte=now - timedelta(days=7)).aggregate(n=Sum("added"))["n"] or 0
    with connection.cursor() as cursor:
        cursor.execute("SELECT reltuples::bigint FROM pg_class WHERE oid='news_article'::regclass")
        count = max(0, cursor.fetchone()[0])
    current["articles_estimate"] = count
    current["new_per_day"] = round(daily / 7, 1)
    current["bytes_per_article_estimate"] = (
        int(current["database_gb"] * GB / max(1, count)) if count else None
    )
    current["retained_days_estimate"] = round(count / max(1, daily / 7), 1) if daily else None
    SiteSettings.objects.filter(pk=1).update(storage=current, paused=current["free_gb"] < config.hard_free_gb)
    return current
