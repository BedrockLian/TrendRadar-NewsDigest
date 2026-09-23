from django.utils import timezone

from app.events.models import Event
from app.news.services import ingest


def test_article_returns_to_its_origin_without_self_loop(reader, feed, item):
    article, _ = ingest(feed, item)
    article_url = f"/news/{article.pk}/"

    direct = reader.get(article_url)
    assert 'class="back archive-back" href="/news/"' in direct.content.decode()

    from_home = reader.get(article_url, {"return": "/"})
    assert 'href="/">← 返回今日工作台' in from_home.content.decode()

    from_event = reader.get(article_url, {"return": "/events/7/?tab=timeline"})
    assert 'href="/events/7/?tab=timeline">← 返回事件' in from_event.content.decode()

    self_loop = reader.get(article_url, {"return": article_url})
    assert 'class="back archive-back" href="/news/"' in self_loop.content.decode()


def test_archive_row_has_one_article_link(reader, feed, item):
    article, _ = ingest(feed, item)
    html = reader.get("/news/").content.decode()
    assert html.count(f'href="/news/{article.pk}/?return=') == 1


def test_events_are_status_filtered_and_paginated(reader):
    now = timezone.now()
    for index in range(22):
        Event.objects.create(name=f"事件 {index}", keywords="事件", status="tracking", overview_at=now)
    Event.objects.create(name="已结束事件", keywords="事件", status="ended")

    first = reader.get("/events/")
    assert first.status_code == 200
    assert first.content.decode().count('class="event-row"') == 20
    assert 'href="?status=tracking&amp;page=2"' in first.content.decode()
    assert "已结束事件" not in first.content.decode()

    second = reader.get("/events/?page=2")
    assert second.content.decode().count('class="event-row"') == 2

    ended = reader.get("/events/?status=ended")
    assert ended.content.decode().count('class="event-row"') == 1
    assert "已结束事件" in ended.content.decode()
    event = Event.objects.get(name="已结束事件")
    assert f"/events/{event.pk}/?return=" in ended.content.decode()
    assert "status%3Dended" in ended.content.decode()
    detail = reader.get(f"/events/{event.pk}/", {"return": "/events/?status=ended"})
    assert 'class="back" href="/events/?status=ended"' in detail.content.decode()
