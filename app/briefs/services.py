from collections import Counter
from datetime import timedelta
from django.db import transaction, connection
from django.utils import timezone
from app.core.models import SiteSettings
from app.news.models import Article, Category
from app.news.services import timestamp
from .models import Briefing, BriefItem


@transaction.atomic
def generate(end=None, catchup=False, revision=False):
    config = SiteSettings.current()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(7142301)")
    end = timestamp(end) or timezone.now()
    base = f"scheduled:{end.isoformat()}"
    previous = Briefing.objects.filter(key__startswith=base).order_by("-revision").first()
    if previous and not revision:
        return previous
    number = previous.revision + 1 if previous else 1
    last = Briefing.objects.filter(end__lt=end, imported=False).order_by("-end").first()
    start = last.end if last else end - timedelta(hours=24)
    qs = Article.objects.filter(updated_at__gt=start, updated_at__lte=end, current__meaningful=True)
    if not revision:
        qs = qs.exclude(current__brief_items__briefing__imported=False)
    candidates = list(
        qs.select_related("current", "feed", "category", "group").order_by("-updated_at")[:3000]
    )
    # Prefer recent reporting, breaking items and configured category weight.
    candidates.sort(
        key=lambda a: (a.breaking, a.category.weight if a.category else 1, a.updated_at), reverse=True
    )
    selected, sources, groups = [], Counter(), set()

    def take(article):
        group = article.group_id or -article.pk
        if group in groups or sources[article.feed_id] >= config.source_limit:
            return False
        selected.append(article)
        sources[article.feed_id] += 1
        groups.add(group)
        return True

    for category in Category.objects.order_by("-weight", "id"):
        count = 0
        for article in candidates:
            if len(selected) >= config.max_items or count >= category.quota:
                break
            if article.category_id == category.pk and take(article):
                count += 1
    for article in candidates:
        if len(selected) >= config.max_items:
            break
        take(article)
    local = timezone.localtime(end)
    label = (
        "补发简报"
        if catchup
        else "早间简报"
        if local.hour < 11
        else "午间简报"
        if local.hour < 17
        else "晚间简报"
    )
    brief = Briefing.objects.create(
        key=f"{base}:v{number}", title=f"{local:%m月%d日} · {label}", start=start, end=end, revision=number
    )
    BriefItem.objects.bulk_create(
        [
            BriefItem(
                briefing=brief,
                version=a.current,
                position=i,
                title=a.title,
                summary=a.current.summary_zh or a.current.summary,
                source=a.feed.name,
                url=a.url,
                group_key=a.group_id,
            )
            for i, a in enumerate(selected, 1)
        ]
    )
    from app.core.tasks import enqueue
    from django.conf import settings

    if settings.AI_KEY:
        for a in selected:
            if not a.current.summary_zh:
                enqueue(
                    "enrich",
                    f"enrich:{a.current_id}:{config.ai_model}",
                    {"version": a.current_id},
                    queue="ai",
                    priority=10,
                    articles=[a],
                )
    return brief
