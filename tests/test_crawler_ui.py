from unittest.mock import patch
from django.utils import timezone
from app.news.crawler import collect
from app.news.models import HourStat, Article
from app.news.services import ingest


def test_304_counts_as_success(config, feed):
    feed.etag = '"v1"'
    feed.save(update_fields=["etag"])
    with patch("app.news.crawler.fetch", return_value=(304, {"etag": '"v1"'}, b"")):
        result = collect(feed.pk, "304-test")
    feed.refresh_from_db()
    stat = HourStat.objects.get()
    assert result["status"] == "not_modified" and stat.requests == stat.successes == 1 and stat.added == 0
    # A conditional hit is a healthy source and keeps the validators it sent.
    assert feed.failures == 0 and feed.last_status == "not_modified:304" and feed.etag == '"v1"'


def test_rate_limit_defers_feed(config, feed):
    with patch("app.news.crawler.fetch", return_value=(429, {"retry-after": "3600"}, b"")):
        collect(feed.pk, "429-test")
    feed.refresh_from_db()
    assert feed.failures == 1 and (feed.next_fetch - timezone.now()).total_seconds() > 3500


def test_valid_rss_and_invalid_do_not_duplicate(config, feed):
    rss = b'<rss version="2.0"><channel><title>test</title><item><title>News</title><link>https://example.org/a</link><guid>a</guid></item></channel></rss>'
    with patch("app.news.crawler.fetch", return_value=(200, {}, rss)):
        collect(feed.pk, "first")
        collect(feed.pk, "second")
    assert Article.objects.count() == 1
    with patch("app.news.crawler.fetch", return_value=(200, {}, b"not rss")):
        assert collect(feed.pk, "broken")["status"] == "failed"


def test_private_routes_require_login(client):
    for route in ["/", "/news/", "/events/", "/briefs/", "/dashboard/", "/settings/"]:
        assert client.get(route).status_code == 302
    assert client.get("/login/").status_code == 200


def test_api_answers_anonymous_callers_with_json(client):
    response = client.get("/api/v1/news/")
    assert response.status_code == 401 and response.json() == {"error": "authentication_required"}
    response = client.post("/api/v1/answer/", data="{}", content_type="application/json")
    assert response.status_code == 401


def test_all_pages_render_real_data(reader, config, feed, item):
    from app.events.models import Event
    from app.events.services import create_node
    from app.briefs.services import generate

    a, _ = ingest(feed, item)
    e = Event.objects.create(name="芯片追踪", keywords="芯片")
    create_node(e, "进展", "", [a.current_id])
    b = generate()
    for route in [
        "/",
        "/news/?q=芯片",
        f"/news/{a.pk}/",
        "/events/",
        f"/events/{e.pk}/",
        "/events/new/",
        f"/events/{e.pk}/edit/",
        "/briefs/",
        f"/briefs/{b.pk}/",
        "/dashboard/",
        "/settings/",
        "/settings/feed/new/",
    ]:
        response = reader.get(route)
        assert response.status_code == 200, route


def test_html_is_escaped(reader, feed, item):
    a, _ = ingest(feed, item)
    a.current.title = "<script>alert('bad')</script>"
    a.current.save()
    response = reader.get(f"/news/{a.pk}/")
    assert b"<script>alert(" not in response.content


def test_csrf_mutations_rejected(django_user_model):
    from django.test import Client

    user = django_user_model.objects.create_user("csrf", password="strong-test-passphrase")
    c = Client(enforce_csrf_checks=True)
    c.force_login(user)
    assert c.post("/action/", {"action": "brief"}).status_code == 403
