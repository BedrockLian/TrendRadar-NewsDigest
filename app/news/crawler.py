import calendar
import time
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import CrawlRun, DomainLease, Feed, HourStat
from .services import ingest, public_url

REDIRECT_CODES = {301, 302, 303, 307, 308}


def fetch(url, headers, *, transport=None):
    # Revalidate every redirect and bound decompressed response bytes.
    # httpx treats *any* 3xx as a redirect, so 304 Not Modified must be handled
    # as a normal result here instead of being followed like a 301.
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False, transport=transport) as client:
        for _ in range(5):
            url = public_url(url)
            with client.stream("GET", url, headers=headers) as response:
                if response.status_code in REDIRECT_CODES:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("重定向缺少目标地址")
                    url = urljoin(url, location)
                    continue
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 5 * 1024 * 1024:
                        raise ValueError("RSS 超过 5MB")
                return response.status_code, dict(response.headers), bytes(data)
    raise ValueError("RSS 重定向过多")


def collect(feed_id, job_key):
    feed = Feed.objects.get(pk=feed_id)
    if not feed.enabled:
        return {"skipped": "disabled"}
    host = urlsplit(feed.url).hostname
    owner = str(uuid.uuid4())
    with transaction.atomic():
        DomainLease.objects.get_or_create(hostname=host)
        lease = DomainLease.objects.select_for_update().get(pk=host)
        if lease.until > timezone.now():
            raise RuntimeError("domain_busy")
        lease.until = timezone.now() + timedelta(minutes=3)
        lease.owner = owner
        lease.save()
    started = time.monotonic()
    counts = {"parsed": 0, "added": 0, "updated": 0, "duplicate": 0}
    status, http_status, error = "failed", 0, ""
    try:
        headers = {
            "User-Agent": "Trendradar/1.0 RSS reader",
            "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml",
        }
        if feed.etag:
            headers["If-None-Match"] = feed.etag
        if feed.modified:
            headers["If-Modified-Since"] = feed.modified
        http_status, response_headers, body = fetch(feed.url, headers)
        if http_status == 429:
            retry = response_headers.get("retry-after", "600")
            try:
                seconds = int(retry)
            except ValueError:
                seconds = int((parsedate_to_datetime(retry) - timezone.now()).total_seconds())
            feed.next_fetch = timezone.now() + timedelta(seconds=max(120, min(seconds, 86400)))
            raise RuntimeError("rate_limited")
        if http_status == 304:
            status = "not_modified"
        elif http_status == 200:
            parsed = feedparser.parse(body)
            if not parsed.get("version") and not parsed.entries:
                raise ValueError("invalid_feed")
            for entry in parsed.entries[:1000]:
                counts["parsed"] += 1
                date = entry.get("published_parsed") or entry.get("updated_parsed")
                item = {
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "guid": entry.get("id", ""),
                    "summary": entry.get("summary", ""),
                    "content": " ".join(x.get("value", "") for x in entry.get("content", [])),
                    "author": entry.get("author", ""),
                    "published_at": datetime.fromtimestamp(calendar.timegm(date), UTC) if date else None,
                }
                try:
                    _, outcome = ingest(feed, item)
                    counts[outcome] += 1
                except ValueError:
                    counts["duplicate"] += 1
            feed.etag = response_headers.get("etag", "")
            feed.modified = response_headers.get("last-modified", "")
            status = "success"
        else:
            raise RuntimeError("http_error")
        feed.failures = 0
        feed.last_success = timezone.now()
    except Exception as exc:
        error = type(exc).__name__
        feed.failures += 1
        if http_status != 429:
            import random

            feed.next_fetch = timezone.now() + timedelta(
                seconds=min(21600, 120 * 2 ** min(feed.failures, 7)) + random.randint(0, 30)
            )
    finally:
        DomainLease.objects.filter(pk=host, owner=owner).update(until=timezone.now())
    elapsed = int((time.monotonic() - started) * 1000)
    now = timezone.now()
    with transaction.atomic():
        feed.last_status = f"{status}:{http_status}"
        feed.save(update_fields=["etag", "modified", "failures", "last_success", "last_status", "next_fetch"])
        CrawlRun.objects.create(
            feed=feed,
            job_key=job_key,
            status=status,
            http_status=http_status,
            elapsed_ms=elapsed,
            error=error,
            **counts,
        )
        stat, _ = HourStat.objects.get_or_create(
            hour=now.replace(minute=0, second=0, microsecond=0), feed=feed
        )
        HourStat.objects.filter(pk=stat.pk).update(
            requests=F("requests") + 1,
            successes=F("successes") + int(status != "failed"),
            elapsed_ms=F("elapsed_ms") + elapsed,
            **{k: F(k) + v for k, v in counts.items()},
        )
    return {"status": status, **counts}
