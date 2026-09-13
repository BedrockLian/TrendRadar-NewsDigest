from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from app.news.services import ingest
from app.news.models import Article, ArticleVersion, Favourite, Tombstone
from app.briefs.services import generate
from app.briefs.models import Briefing, BriefItem
from app.events.models import Event
from app.events.services import create_node, merge_nodes, split_node
from app.core.storage import maintain
from app.core.tasks import enqueue, claim, execute, schedule_once
from app.core.models import Job


def test_brief_is_frozen_and_deduplicated(config, feed, item):
    a, _ = ingest(feed, item)
    end = timezone.now()
    b = generate(end=end)
    assert b.items.count() == 1
    assert generate(end=end).pk == b.pk
    ArticleVersion.objects.filter(pk=a.current_id).update(title_zh="之后生成的中文标题")
    assert b.items.get().title == item["title"]
    later = generate(end=end + timedelta(minutes=1))
    assert later.items.count() == 0


def test_cleanup_protects_citations_favourites_and_jobs(config, feed, item):
    articles = []
    for i in range(5):
        a, _ = ingest(feed, {**item, "url": f"https://example.org/{i}", "guid": str(i)})
        Article.objects.filter(pk=a.pk).update(first_seen=timezone.now() - timedelta(days=200))
        articles.append(a)
    brief = Briefing.objects.create(key="protected", title="简报", start=timezone.now(), end=timezone.now())
    BriefItem.objects.create(
        briefing=brief,
        version=articles[0].current,
        position=1,
        title="固定标题",
        summary="",
        source="源",
        url=articles[0].url,
    )
    event = Event.objects.create(name="事件", keywords="芯片")
    create_node(event, "进展", "", [articles[1].current_id])
    Favourite.objects.create(version=articles[2].current)
    enqueue("enrich", "pending-protection", queue="ai", articles=[articles[3]])
    with patch("app.core.storage.measure", return_value={"free_gb": 10, "database_gb": 1}):
        result = maintain()
    assert result["removed"] == 1
    assert Article.objects.filter(pk__in=[x.pk for x in articles[:4]]).count() == 4
    assert Tombstone.objects.filter(key=articles[4].url_hash).exists()
    assert ingest(feed, {**item, "url": "https://example.org/4", "guid": "4"})[0] is None


def test_hard_capacity_pauses_workers(config):
    with patch("app.core.storage.measure", return_value={"free_gb": 5, "database_gb": 1}):
        maintain()
    enqueue("collect", "hard-pause", queue="collect")
    assert claim("collect") is None
    with patch("app.core.storage.measure", return_value={"free_gb": 10, "database_gb": 1}):
        maintain()
    assert claim("collect") is not None


def test_event_merge_and_split_preserve_reports(feed, item):
    a, _ = ingest(feed, item)
    b, _ = ingest(feed, {**item, "url": "https://example.org/2", "guid": "2"})
    event = Event.objects.create(name="芯片事件", keywords="芯片")
    first = create_node(event, "首个进展", "", [a.current_id])
    second = create_node(event, "第二项进展", "", [b.current_id])
    merged = merge_nodes(first.pk, second.pk)
    assert merged.reports.count() == 2
    split = split_node(merged.pk, [b.current_id], "单独进展")
    assert merged.reports.count() == 1 and split.reports.count() == 1 and split.confirmed


def test_expired_lease_recovers_and_completed_not_reclaimed(config):
    enqueue("test", "lease", queue="maintenance")
    first = claim("maintenance")
    Job.objects.filter(pk=first.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
    second = claim("maintenance")
    assert second.pk == first.pk and second.owner != first.owner
    with patch("app.core.tasks.dispatch", return_value={"ok": True}):
        execute(second)
    assert claim("maintenance") is None


def test_schedule_catchup_single_brief(config):
    config.last_schedule = timezone.now() - timedelta(days=2)
    config.save()
    schedule_once()
    jobs = Job.objects.filter(kind="brief")
    assert jobs.count() == 1 and jobs.get().payload["catchup"]
    schedule_once()
    assert jobs.count() == 1
