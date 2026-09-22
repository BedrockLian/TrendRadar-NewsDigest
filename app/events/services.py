import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from app.core.tasks import enqueue
from app.news.models import ArticleVersion, Feed
from app.news.services import search_articles

from .models import Candidate, Event, Node, NodeReport

EVENT_AUTOMATION_VERSION = "1"


def enqueue_candidate(candidate):
    return enqueue(
        "event_ai",
        f"event-auto:{EVENT_AUTOMATION_VERSION}:{candidate.event_id}:{candidate.article_id}",
        {"event": candidate.event_id, "article": candidate.article_id},
        queue="ai",
        priority=20,
        articles=[candidate.article_id],
    )


def discover(event_id=None, full=False):
    found = 0
    events = Event.objects.filter(status="tracking")
    if event_id:
        events = events.filter(pk=event_id)
    for event in events:
        if settings.AI_KEY:
            for candidate in event.candidates.filter(status="pending").only("id", "event_id", "article_id")[
                :2000
            ]:
                enqueue_candidate(candidate)
        ids = set()
        start = event.start
        if event.last_scan and not full:
            start = max(start or event.last_scan, event.last_scan - timedelta(hours=1))
        for keyword in re.split(r"[,，\n]", event.keywords):
            keyword = keyword.strip()
            if len(keyword) < 2:
                continue
            cursor = None
            for _ in range(20):
                rows, cursor = search_articles(keyword, start=start, end=event.end, cursor=cursor, limit=100)
                ids.update(a.pk for a in rows)
                if not cursor:
                    break
        for article_id in sorted(ids):
            candidate, created = Candidate.objects.get_or_create(
                event=event, article_id=article_id, defaults={"reason": "关键词命中，等待确认"}
            )
            if created:
                found += 1
            if candidate.status == "pending" and settings.AI_KEY:
                enqueue_candidate(candidate)
        event.last_scan = timezone.now()
        event.save(update_fields=["last_scan"])
    return {"candidates": found}


@transaction.atomic
def confirm_node(node_id):
    node = Node.objects.select_for_update().get(pk=node_id)
    if not node.reports.exists():
        raise ValueError("节点必须引用至少一篇报道")
    node.confirmed = True
    node.save(update_fields=["confirmed"])
    article_ids = node.reports.values_list("version__article_id", flat=True)
    Candidate.objects.filter(event=node.event, article_id__in=article_ids).update(status="accepted")
    refresh_overview(node.event_id)
    return node


def refresh_overview(event_id):
    event = Event.objects.get(pk=event_id)
    nodes = list(event.nodes.filter(confirmed=True)[:5])
    event.overview = "\n".join(
        f"{timezone.localtime(node.occurred_at):%m-%d %H:%M} {node.title}" for node in nodes
    )
    event.overview_at = timezone.now() if nodes else None
    event.save(update_fields=["overview", "overview_at"])


@transaction.atomic
def create_node(event, title, summary, versions, occurred_at=None, time_basis="reported", confirmed=True):
    rows = list(ArticleVersion.objects.select_for_update().filter(pk__in=versions))
    if not rows or len(rows) != len(set(versions)):
        raise ValueError("报道版本不存在")
    node = Node.objects.create(
        event=event,
        title=title,
        summary=summary,
        occurred_at=occurred_at or rows[0].article.published_at or rows[0].created_at,
        time_basis=time_basis,
        confirmed=False,
        edited=True,
    )
    NodeReport.objects.bulk_create([NodeReport(node=node, version=v) for v in rows])
    if confirmed:
        node = confirm_node(node.pk)
    return node


@transaction.atomic
def remove_node(node_id):
    node = Node.objects.select_for_update().get(pk=node_id)
    event_id = node.event_id
    article_ids = list(node.reports.values_list("version__article_id", flat=True))
    node.delete()
    still_linked = set(
        NodeReport.objects.filter(
            node__event_id=event_id,
            node__confirmed=True,
            version__article_id__in=article_ids,
        ).values_list("version__article_id", flat=True)
    )
    Candidate.objects.filter(
        event_id=event_id,
        article_id__in=set(article_ids) - still_linked,
    ).update(status="rejected")
    refresh_overview(event_id)


@transaction.atomic
def merge_nodes(target_id, source_id):
    nodes = list(Node.objects.select_for_update().filter(pk__in=[target_id, source_id]).order_by("id"))
    if len(nodes) != 2 or nodes[0].event_id != nodes[1].event_id:
        raise ValueError("只能合并同一事件的两个节点")
    target = next(n for n in nodes if n.pk == target_id)
    source = next(n for n in nodes if n.pk == source_id)
    for report in source.reports.all():
        NodeReport.objects.get_or_create(node=target, version=report.version)
    target.summary = "\n".join(filter(None, [target.summary, source.summary]))
    target.edited = True
    target.save()
    source.delete()
    refresh_overview(target.event_id)
    return target


@transaction.atomic
def split_node(node_id, version_ids, title):
    node = Node.objects.select_for_update().get(pk=node_id)
    selected = node.reports.filter(version_id__in=version_ids)
    if not selected.exists() or selected.count() >= node.reports.count():
        raise ValueError("拆分需保留原节点至少一篇报道")
    new = create_node(
        node.event,
        title,
        "",
        list(selected.values_list("version_id", flat=True)),
        occurred_at=node.occurred_at,
        time_basis=node.time_basis,
        confirmed=node.confirmed,
    )
    selected.delete()
    refresh_overview(node.event_id)
    return new


def boost(event_id):
    ids = Candidate.objects.filter(event_id=event_id, status="accepted").values_list(
        "article__feed_id", flat=True
    )
    ids2 = NodeReport.objects.filter(node__event_id=event_id, node__confirmed=True).values_list(
        "version__article__feed_id", flat=True
    )
    return Feed.objects.filter(pk__in=set(ids) | set(ids2)).update(
        boost_until=timezone.now() + timedelta(hours=6), next_fetch=timezone.now()
    )
