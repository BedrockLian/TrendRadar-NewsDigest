from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from app.briefs.models import Briefing, BriefItem
from app.briefs.services import generate
from app.core.models import Job
from app.core.storage import maintain
from app.core.tasks import claim, enqueue, execute, schedule_once
from app.events.models import Candidate, Event
from app.events.services import create_node, discover, merge_nodes, remove_node, split_node
from app.news.models import Article, ArticleVersion, Favourite, Tombstone
from app.news.services import ingest


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


def test_new_article_enqueues_enrichment_after_commit(config, feed, item, django_capture_on_commit_callbacks):
    english = {**item, "title": "New foreign report", "summary": "News requiring translation."}
    with patch("app.core.tasks.enqueue") as enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            article, _ = ingest(feed, english)
    enqueue.assert_called_once()
    assert enqueue.call_args.args[:2] == (
        "enrich",
        f"enrich:{article.current_id}:{config.ai_model}",
    )
    assert enqueue.call_args.kwargs["priority"] == 30


def test_brief_promotes_an_existing_delayed_translation(config, feed, item):
    english = {**item, "title": "Untranslated report", "summary": "A report awaiting translation."}
    article, _ = ingest(feed, english)
    key = f"enrich:{article.current_id}:{config.ai_model}"
    job = enqueue("enrich", key, {"version": article.current_id}, queue="ai", priority=30)
    Job.objects.filter(pk=job.pk).update(
        available_at=timezone.now() + timedelta(days=1), error="今日AI额度已用完，次日继续"
    )
    with override_settings(AI_KEY="configured"):
        generate(end=timezone.now() + timedelta(minutes=1))
    job.refresh_from_db()
    assert job.priority == 10
    assert job.available_at <= timezone.now()


def test_brief_retries_a_delayed_top_priority_translation(config, feed, item):
    article, _ = ingest(feed, {**item, "title": "Still untranslated", "summary": "An untranslated report."})
    key = f"enrich:{article.current_id}:{config.ai_model}"
    job = enqueue("enrich", key, {"version": article.current_id}, queue="ai", priority=10)
    Job.objects.filter(pk=job.pk).update(available_at=timezone.now() + timedelta(days=1))
    enqueue("enrich", key, {"version": article.current_id}, queue="ai", priority=10)
    job.refresh_from_db()
    assert job.available_at <= timezone.now()


def test_missing_localization_reopens_a_completed_enrichment(config, feed, item):
    english = {**item, "title": "Japanese report", "summary": "A report requiring translation."}
    article, _ = ingest(feed, english)
    key = f"enrich:{article.current_id}:{config.ai_model}"
    job = enqueue("enrich", key, {"version": article.current_id}, queue="ai", priority=30)
    Job.objects.filter(pk=job.pk).update(status="completed", finished_at=timezone.now())
    enqueue("enrich", key, {"version": article.current_id}, queue="ai", priority=10)
    job.refresh_from_db()
    assert job.status == "pending"
    assert job.priority == 10
    assert job.finished_at is None


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


def test_event_discovery_requeues_existing_pending_candidates(config, feed, item):
    article, _ = ingest(feed, item)
    event = Event.objects.create(name="芯片事件", keywords="x")
    Candidate.objects.create(event=event, article=article)
    with override_settings(AI_KEY="configured"):
        discover(event.pk)
    job = Job.objects.get(kind="event_ai", payload__event=event.pk, payload__article=article.pk)
    assert job.key == f"event-auto:1:{event.pk}:{article.pk}"
    assert job.priority == 20


def test_removed_ai_node_is_rejected_and_leaves_timeline(feed, item):
    article, _ = ingest(feed, item)
    event = Event.objects.create(name="芯片事件", keywords="芯片")
    candidate = Candidate.objects.create(event=event, article=article, status="accepted")
    node = create_node(event, "自动收录进展", "", [article.current_id])
    remove_node(node.pk)
    candidate.refresh_from_db()
    event.refresh_from_db()
    assert candidate.status == "rejected"
    assert not event.nodes.exists()
    assert event.overview == ""
    assert event.overview_at is None


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
    discovery = Job.objects.get(kind="event_discovery")
    assert discovery.queue == "ai" and discovery.priority == 5
    schedule_once()
    assert Job.objects.filter(kind="event_discovery").count() == 1
