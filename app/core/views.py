import json
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db import connection, transaction
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDay
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.signing import BadSignature
from .forms import FeedForm, EventForm, SettingsForm
from .models import Job, SiteSettings, ImportRun
from .tasks import enqueue
from app.news.models import Article, ArticleVersion, Feed, Category, HourStat, Favourite, StoryGroup
from app.news.services import search_articles, article_dict, timestamp
from app.briefs.models import Briefing
from app.events.models import Event, Node, Candidate
from app.events.services import confirm_node, create_node, merge_nodes, split_node, boost, refresh_overview
from app.ai.models import UsageDay, Conversation


def context(**extra):
    return {
        "config": SiteSettings.current(),
        "ai_enabled": bool(settings.AI_KEY),
        "today": timezone.localdate(),
        **extra,
    }


def home(request):
    brief = Briefing.objects.prefetch_related("items").first()
    rows = Article.objects.select_related("current", "feed", "category").filter(current__isnull=False)
    if brief:
        rows = rows.filter(first_seen__gt=brief.end)
    return render(
        request,
        "home.html",
        context(
            title="今日工作台",
            active="home",
            brief=brief,
            articles=rows.order_by("-first_seen")[:30],
            events=Event.objects.filter(status="tracking").order_by("-created_at")[:6],
            breaking=Article.objects.select_related("current", "feed")
            .filter(breaking=True, first_seen__gte=timezone.now() - timedelta(hours=12))
            .order_by("-first_seen")[:3],
        ),
    )


def news(request):
    error, rows, next_cursor = "", [], None
    try:
        rows, next_cursor = search_articles(
            request.GET.get("q", ""),
            feed=request.GET.get("feed"),
            category=request.GET.get("category"),
            start=request.GET.get("start") or None,
            end=request.GET.get("end") or None,
            cursor=request.GET.get("cursor"),
        )
    except ValueError, BadSignature:
        error = "筛选条件无效，请使用至少两个字符并检查日期。"
    query = request.GET.copy()
    query["cursor"] = next_cursor or ""
    return render(
        request,
        "news.html",
        context(
            title="新闻归档",
            active="news",
            articles=rows,
            feeds=Feed.objects.order_by("name"),
            categories=Category.objects.all(),
            error=error,
            next_url="?" + query.urlencode() if next_cursor else None,
        ),
    )


def article(request, pk):
    row = get_object_or_404(Article.objects.select_related("current", "feed", "category"), pk=pk)
    version = row.current
    if request.GET.get("version"):
        version = get_object_or_404(row.versions, pk=request.GET["version"])
    related = (
        Article.objects.select_related("current", "feed")
        .filter(group_id=row.group_id)
        .exclude(pk=row.pk)[:30]
        if row.group_id
        else []
    )
    return render(
        request,
        "article.html",
        context(
            title=row.title,
            active="news",
            article=row,
            version=version,
            versions=row.versions.order_by("-created_at")[:30],
            favourite=Favourite.objects.filter(version=version).exists(),
            related=related,
            group_choices=Article.objects.select_related("current", "feed")
            .filter(current__isnull=False, category=row.category)
            .exclude(pk=row.pk)
            .order_by("-first_seen")[:40],
            events=Event.objects.filter(status="tracking"),
        ),
    )


def briefs(request, pk=None):
    if pk:
        return render(
            request,
            "brief.html",
            context(
                title="新闻简报",
                active="briefs",
                brief=get_object_or_404(Briefing.objects.prefetch_related("items"), pk=pk),
            ),
        )
    return render(
        request,
        "briefs.html",
        context(title="新闻简报", active="briefs", briefs=Briefing.objects.order_by("-end")[:120]),
    )


def events(request, pk=None):
    if pk:
        event = get_object_or_404(Event, pk=pk)
        return render(
            request,
            "event.html",
            context(
                title=event.name,
                active="events",
                event=event,
                nodes=event.nodes.filter(confirmed=True).prefetch_related("reports__version__article__feed"),
                drafts=event.nodes.filter(confirmed=False).prefetch_related(
                    "reports__version__article__feed"
                ),
                candidates=event.candidates.filter(status="pending").select_related(
                    "article__current", "article__feed"
                )[:100],
                oldest=Article.objects.order_by("first_seen").values_list("first_seen", flat=True).first(),
            ),
        )
    return render(
        request,
        "events.html",
        context(
            title="重大事件",
            active="events",
            events=Event.objects.annotate(
                pending=Count("candidates", filter=Q(candidates__status="pending"))
            ).order_by("-created_at"),
        ),
    )


def edit_event(request, pk=None):
    instance = get_object_or_404(Event, pk=pk) if pk else None
    form = EventForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        enqueue("events", f"manual-events:{uuid.uuid4()}", {"event": event.pk})
        messages.success(request, "事件已保存，系统将查找关联报道。")
        return redirect("event", pk=event.pk)
    return render(
        request, "form.html", context(title="编辑事件" if pk else "建立事件", active="events", form=form)
    )


def stats_data(request):
    days = min(365, max(1, int(request.GET.get("days", 1))))
    start = timestamp(request.GET.get("start")) or timezone.now() - timedelta(days=days)
    end = timestamp(request.GET.get("end")) or timezone.now()
    if start >= end or end - start > timedelta(days=366):
        raise ValueError("时间范围应在一年以内")
    qs = HourStat.objects.filter(hour__gte=start, hour__lt=end)
    fields = ["requests", "successes", "parsed", "added", "updated", "duplicate", "elapsed_ms"]
    totals = qs.aggregate(**{f: Sum(f) for f in fields})
    group = "hour"
    if request.GET.get("bucket") == "day" or end - start > timedelta(days=3):
        qs = qs.annotate(day=TruncDay("hour"))
        group = "day"
    series = list(qs.values(group).annotate(**{f: Sum(f) for f in fields}).order_by(group))
    for row in series:
        row["time"] = row.pop(group).isoformat()
    return {
        "totals": {k: v or 0 for k, v in totals.items()},
        "series": series,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bucket": group,
    }


def dashboard(request):
    try:
        data = stats_data(request)
    except ValueError:
        data = {"totals": {}, "series": []}
        messages.error(request, "统计时间范围无效")
    jobs = list(Job.objects.values("queue", "status").annotate(count=Count("id")))
    for job in jobs:
        job["queue"] = {"collect": "新闻采集", "ai": "中文内容与问答", "maintenance": "简报与维护"}.get(
            job["queue"], job["queue"]
        )
        job["status"] = {
            "pending": "待处理",
            "running": "处理中",
            "completed": "已完成",
            "failed": "失败",
        }.get(job["status"], job["status"])
    return render(
        request,
        "dashboard.html",
        context(
            title="采集仪表盘",
            active="dashboard",
            data=data,
            feeds=Feed.objects.order_by("-failures", "name"),
            usage=UsageDay.objects.filter(day=timezone.localdate()).first(),
            jobs=jobs,
            imports=ImportRun.objects.order_by("-id")[:5],
        ),
    )


def preferences(request):
    form = SettingsForm(request.POST or None, instance=SiteSettings.current())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "设置已保存")
        return redirect("settings")
    return render(
        request,
        "settings.html",
        context(
            title="设置",
            active="settings",
            form=form,
            feeds=Feed.objects.select_related("category").order_by("name"),
        ),
    )


def edit_feed(request, pk=None):
    form = FeedForm(request.POST or None, instance=get_object_or_404(Feed, pk=pk) if pk else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "订阅源已保存")
        return redirect("settings")
    return render(
        request,
        "form.html",
        context(title="编辑订阅源" if pk else "添加订阅源", active="settings", form=form),
    )


@require_POST
def action(request):
    is_json = request.content_type == "application/json"
    try:
        data = json.loads(request.body) if is_json else request.POST
    except ValueError:
        return JsonResponse({"error": "invalid_json"}, status=400)
    name = data.get("action")
    target = data.get("return", "/")
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    job = None

    def ids_field(key):
        values = data.get(key, []) if is_json else data.getlist(key)
        if isinstance(values, str):
            values = values.split(",")
        return [int(x) for value in values for x in str(value).split(",") if x.strip()]

    try:
        with transaction.atomic():
            if name == "favourite":
                v = get_object_or_404(ArticleVersion, pk=int(data["version"]))
                Article.objects.select_for_update().get(pk=v.article_id)
                item, created = Favourite.objects.get_or_create(version=v)
                if not created:
                    item.delete()
            elif name == "enrich":
                v = get_object_or_404(ArticleVersion, pk=int(data["version"]))
                if not settings.AI_KEY:
                    raise ValueError("请先在服务器配置AI密钥")
                job = enqueue(
                    "enrich",
                    f"manual-enrich:{v.pk}:{uuid.uuid4()}",
                    {"version": v.pk},
                    queue="ai",
                    articles=[v.article_id],
                )
            elif name == "collect":
                f = get_object_or_404(Feed, pk=int(data["feed"]))
                job = enqueue(
                    "collect", f"manual-feed:{f.pk}:{uuid.uuid4()}", {"feed": f.pk}, queue="collect"
                )
            elif name == "brief":
                payload = {}
                if data.get("brief"):
                    b = get_object_or_404(Briefing, pk=int(data["brief"]))
                    payload = {"end": b.end.isoformat(), "revision": True}
                job = enqueue("brief", f"manual-brief:{uuid.uuid4()}", payload, priority=10)
            elif name == "seed":
                e = get_object_or_404(Event, pk=int(data["event"]))
                v = get_object_or_404(ArticleVersion, pk=int(data["version"]))
                Article.objects.select_for_update().get(pk=v.article_id)
                create_node(e, v.title_zh or v.title, v.summary_zh or v.summary, [v.pk])
            elif name == "confirm":
                confirm_node(int(data["node"]))
            elif name == "reject_candidate":
                get_object_or_404(Candidate, pk=int(data["candidate"]))
                Candidate.objects.filter(pk=int(data["candidate"])).update(status="rejected")
            elif name == "reject_draft":
                get_object_or_404(Node, pk=int(data["node"]), confirmed=False).delete()
            elif name == "accept_candidate":
                c = get_object_or_404(
                    Candidate.objects.select_related("article__current"), pk=int(data["candidate"])
                )
                v = c.article.current
                Article.objects.select_for_update().get(pk=c.article_id)
                create_node(c.event, v.title_zh or v.title, v.summary_zh or v.summary, [v.pk])
            elif name == "boost":
                boost(int(data["event"]))
            elif name == "merge_node":
                merge_nodes(int(data["node"]), int(data["source"]))
            elif name == "split_node":
                split_node(int(data["node"]), ids_field("versions"), data["title"][:1000])
            elif name == "edit_node":
                n = get_object_or_404(Node.objects.select_for_update(), pk=int(data["node"]))
                n.title, n.summary = data["title"][:1000], data["summary"][:20000]
                n.occurred_at = timestamp(data["occurred_at"]) or n.occurred_at
                n.time_basis = "occurred" if data.get("time_basis") == "occurred" else "reported"
                n.edited = True
                n.save()
                refresh_overview(n.event_id)
            elif name == "group":
                ids = ids_field("articles")
                rows = list(Article.objects.select_for_update().filter(pk__in=ids))
                if len(rows) < 2:
                    raise ValueError("至少选择两篇报道")
                group = StoryGroup.objects.create(title=rows[0].title)
                Article.objects.filter(pk__in=ids).update(group=group)
            elif name == "ungroup":
                Article.objects.filter(pk=int(data["article"])).update(group=None)
            elif name == "capacity":
                job = enqueue("capacity", f"manual-capacity:{uuid.uuid4()}", priority=0)
            else:
                raise ValueError("未知操作")
        if is_json:
            return JsonResponse({"ok": True, "job": str(job.pk) if job else None}, status=202 if job else 200)
        messages.success(request, "操作已保存；后台任务可在仪表盘查看。")
    except (ValueError, KeyError) as exc:
        if is_json:
            return JsonResponse({"error": str(exc)}, status=400)
        messages.error(request, str(exc))
    return redirect(target)


def queue_fragment(request):
    return render(
        request,
        "queue.html",
        {
            "pending": Job.objects.filter(status="pending").count(),
            "running": Job.objects.filter(status="running").count(),
            "failed": Job.objects.filter(status="failed").count(),
        },
    )


def api_news(request):
    try:
        rows, cursor = search_articles(
            request.GET.get("q", ""),
            cursor=request.GET.get("cursor"),
            feed=request.GET.get("feed"),
            category=request.GET.get("category"),
            start=request.GET.get("start") or None,
            end=request.GET.get("end") or None,
        )
        return JsonResponse({"items": [article_dict(a) for a in rows], "next_cursor": cursor})
    except ValueError, BadSignature:
        return JsonResponse({"error": "invalid_query"}, status=400)


def api_stats(request):
    try:
        return JsonResponse(stats_data(request))
    except ValueError:
        return JsonResponse({"error": "invalid_range"}, status=400)


def api_job(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return JsonResponse({"id": str(job.pk), "status": job.status, "result": job.result, "error": job.error})


@require_POST
def api_answer(request):
    try:
        payload = json.loads(request.body)
        question = str(payload["question"])
        if not 2 <= len(question) <= 2000:
            raise ValueError()
        if not settings.AI_KEY:
            return JsonResponse({"error": "尚未配置AI密钥"}, status=503)
        if SiteSettings.current().paused:
            return JsonResponse({"error": "空间不足，AI处理已暂停"}, status=503)
        conversation = (
            get_object_or_404(Conversation, pk=payload["conversation"])
            if payload.get("conversation")
            else Conversation.objects.create(title=question[:300])
        )
        if Job.objects.filter(
            kind="answer", payload__conversation=conversation.pk, status__in=["pending", "running"]
        ).exists():
            return JsonResponse({"error": "请等待上一条问题完成"}, status=409)
        job = enqueue(
            "answer",
            f"answer:{uuid.uuid4()}",
            {"conversation": conversation.pk, "question": question},
            queue="ai",
            priority=5,
        )
        return JsonResponse({"job": str(job.pk), "conversation": conversation.pk}, status=202)
    except ValueError, KeyError, TypeError:
        return JsonResponse({"error": "问题格式无效"}, status=400)


def job_stream(request, pk):
    get_object_or_404(Job, pk=pk)

    async def stream():
        import asyncio
        from asgiref.sync import sync_to_async

        last = None
        for _ in range(300):
            state = await sync_to_async(lambda: Job.objects.values("status", "result", "error").get(pk=pk))()
            if state != last:
                yield "event: state\ndata: " + json.dumps(state, ensure_ascii=False) + "\n\n"
                last = state
            else:
                yield ": heartbeat\n\n"
            if state["status"] in ("completed", "failed"):
                return
            await asyncio.sleep(1)

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def api_briefs(request):
    return JsonResponse(
        {"items": list(Briefing.objects.values("id", "title", "start", "end", "revision")[:100])}
    )


def api_events(request):
    return JsonResponse({"items": list(Event.objects.values("id", "name", "status", "overview")[:100])})


@login_not_required
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
