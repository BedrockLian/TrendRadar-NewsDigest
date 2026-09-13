import logging
import threading
import time
import uuid
from datetime import timedelta
from django.db import close_old_connections, connection, transaction
from django.utils import timezone
from .models import Job, SiteSettings

log = logging.getLogger(__name__)


def enqueue(kind, key, payload=None, *, queue="maintenance", priority=100, articles=()):
    job, created = Job.objects.get_or_create(
        key=key, defaults={"kind": kind, "queue": queue, "payload": payload or {}, "priority": priority}
    )
    if created and articles:
        job.articles.add(*articles)
    return job


@transaction.atomic
def claim(queue):
    now = timezone.now()
    expired = Job.objects.filter(status="running", lease_until__lt=now)
    expired.filter(attempts__gte=4).update(
        status="failed", error="执行租约过期，已达重试上限", finished_at=now
    )
    expired.filter(attempts__lt=4).update(status="pending", owner=None, lease_until=None)
    if queue in ("collect", "ai") and SiteSettings.current().paused:
        return None
    if queue == "collect":
        SiteSettings.objects.select_for_update().get(pk=1)
        if Job.objects.filter(queue="collect", status="running", lease_until__gt=now).count() >= 6:
            return None
    if queue == "ai":
        # Singleton row provides a global concurrency limit, including multiple hosts.
        config = SiteSettings.objects.select_for_update().get(pk=1)
        if (
            Job.objects.filter(queue="ai", status="running", lease_until__gt=now).count()
            >= config.ai_concurrency
        ):
            return None
    job = (
        Job.objects.select_for_update(skip_locked=True)
        .filter(queue=queue, status="pending", available_at__lte=now)
        .order_by("priority", "available_at")
        .first()
    )
    if job:
        job.status = "running"
        job.owner = uuid.uuid4()
        job.lease_until = now + timedelta(seconds=90)
        job.attempts += 1
        job.save()
    return job


def dispatch(job):
    if job.kind == "collect":
        from app.news.crawler import collect

        return collect(job.payload["feed"], job.key)
    if job.kind == "brief":
        from app.briefs.services import generate

        return {"briefing": generate(**job.payload).pk}
    if job.kind == "capacity":
        from .storage import maintain

        return maintain()
    if job.kind == "events":
        from app.events.services import discover

        return discover(job.payload.get("event"), full=bool(job.payload.get("event")))
    if job.kind == "prepare_ai":
        from app.ai.services import prepare_ai

        return prepare_ai()
    if job.kind in ("enrich", "event_ai", "answer"):
        from app.ai.services import run_job

        return run_job(job)
    raise ValueError("未知任务类型")


def execute(job):
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(20):
            close_old_connections()
            Job.objects.filter(pk=job.pk, owner=job.owner, status="running").update(
                lease_until=timezone.now() + timedelta(seconds=90)
            )
        connection.close()

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        result = dispatch(job) or {}
        Job.objects.filter(pk=job.pk, owner=job.owner).update(
            status="completed", result=result, finished_at=timezone.now(), lease_until=None, error=""
        )
    except Exception as exc:
        if type(exc).__name__ == "BudgetExceeded":
            tomorrow = (timezone.localtime() + timedelta(days=1)).replace(
                hour=0, minute=5, second=0, microsecond=0
            )
            Job.objects.filter(pk=job.pk, owner=job.owner).update(
                status="pending",
                attempts=0,
                available_at=tomorrow,
                lease_until=None,
                error="今日AI额度已用完，次日继续",
            )
            return
        # Never include provider payloads, feed content or secrets in task errors.
        log.warning("job_failed kind=%s id=%s error=%s", job.kind, job.pk, type(exc).__name__)
        Job.objects.filter(pk=job.pk, owner=job.owner).update(
            status="failed" if job.attempts >= 4 else "pending",
            error=type(exc).__name__,
            lease_until=None,
            available_at=timezone.now() + timedelta(seconds=min(3600, 30 * 2**job.attempts)),
        )
    finally:
        stop.set()
        thread.join(timeout=5)


def worker(queue, once=False):
    while True:
        close_old_connections()
        job = claim(queue)
        if job:
            execute(job)
        if once:
            return
        if not job:
            time.sleep(2)


@transaction.atomic
def schedule_once():
    from app.news.models import Feed
    from app.news.services import timestamp
    from zoneinfo import ZoneInfo

    now = timezone.now()
    config = SiteSettings.current()
    config = SiteSettings.objects.select_for_update().get(pk=config.pk)
    for feed in Feed.objects.select_for_update(skip_locked=True).filter(enabled=True, next_fetch__lte=now):
        if Job.objects.filter(
            queue="collect", payload__feed=feed.pk, status__in=["pending", "running"]
        ).exists():
            continue
        enqueue("collect", f"feed:{feed.pk}:{int(now.timestamp() // 60)}", {"feed": feed.pk}, queue="collect")
        seconds = 120 if feed.boost_until and feed.boost_until > now else max(120, feed.interval_seconds)
        feed.next_fetch = now + timedelta(seconds=seconds)
        feed.save(update_fields=["next_fetch"])
    zone = ZoneInfo("Asia/Shanghai")
    due = []
    day = max(config.last_schedule, now - timedelta(days=7)).astimezone(zone).date()
    while day <= now.astimezone(zone).date():
        for slot in config.briefing_times:
            moment = timestamp(f"{day.isoformat()}T{slot}:00+08:00")
            if config.last_schedule < moment <= now:
                due.append(moment)
        day += timedelta(days=1)
    if due:
        cutoff = max(due)
        enqueue(
            "brief",
            f"brief:{cutoff.isoformat()}",
            {"end": cutoff.isoformat(), "catchup": len(due) > 1},
            priority=10,
        )
    enqueue("capacity", f"capacity:{now:%Y%m%d%H}", priority=0)
    enqueue("events", f"events:{int(now.timestamp() // 600)}", priority=50)
    enqueue("prepare_ai", f"prepare-ai:{int(now.timestamp() // 600)}", priority=60)
    config.last_schedule = now
    config.save(update_fields=["last_schedule"])


def scheduler(once=False):
    while True:
        schedule_once()
        if once:
            return
        time.sleep(15)
