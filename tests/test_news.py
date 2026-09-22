from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from app.news.models import ArticleVersion, Feed
from app.news.services import canonical_url, ingest, search_articles


def test_duplicate_identity_and_versions(feed, item):
    article, status = ingest(feed, item)
    assert status == "added"
    original = article.current_id
    again, status = ingest(feed, {**item, "url": "https://example.org/news/1?utm_medium=reader"})
    assert again.pk == article.pk and status == "duplicate"
    updated, status = ingest(feed, {**item, "summary": "新一代芯片宣布正式发售。"})
    assert status == "updated" and updated.current_id != original
    assert ArticleVersion.objects.count() == 2
    assert ArticleVersion.objects.get(pk=original).summary == item["summary"]


def test_cross_feed_same_url_keeps_sources(feed, item):
    second = Feed.objects.create(slug="other", name="另一来源", url="https://other.org/rss")
    a, _ = ingest(feed, item)
    b, _ = ingest(second, {**item, "guid": "other-guid"})
    assert a.pk == b.pk
    assert a.identities.count() == 2
    c, _ = ingest(second, {**item, "guid": "independent", "url": "https://other.org/report"})
    assert c.pk != a.pk


def test_chinese_search_cursor_and_short_rejection(feed, item):
    for i in range(45):
        ingest(feed, {**item, "url": f"https://example.org/{i}", "guid": str(i)})
    rows, cursor = search_articles("人工智能", limit=40)
    assert len(rows) == 40 and cursor
    rest, next_cursor = search_articles("人工智能", cursor=cursor)
    assert len(rest) == 5 and not next_cursor
    assert not ({x.pk for x in rows} & {x.pk for x in rest})
    with pytest.raises(ValueError):
        search_articles("人")


@pytest.mark.django_db(transaction=True)
def test_parallel_ingest_global_url(feed, item):
    def run(_):
        close_old_connections()
        try:
            return ingest(Feed.objects.get(pk=feed.pk), item)[0].pk
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        ids = list(pool.map(run, range(3)))
    assert len(set(ids)) == 1 and ArticleVersion.objects.count() == 1


def test_url_preserves_meaningful_parameters():
    assert canonical_url("https://EXAMPLE.org/a?id=2&utm_source=x#top") == "https://example.org/a?id=2"
    with pytest.raises(ValueError):
        canonical_url("javascript:alert(1)")


def test_historical_import_does_not_replace_newer_version(feed, item):
    a, _ = ingest(feed, item)
    original = a.current_id
    a, _ = ingest(
        feed,
        {**item, "summary": "旧摘要", "first_seen": (timezone.now() - timedelta(days=10)).isoformat()},
        imported=True,
    )
    assert a.current_id == original
