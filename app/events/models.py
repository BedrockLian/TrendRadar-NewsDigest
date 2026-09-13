from django.db import models
from django.utils import timezone


class Event(models.Model):
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    keywords = models.TextField(help_text="使用逗号分隔关键词与别名")
    status = models.CharField(
        max_length=20,
        default="tracking",
        choices=[("tracking", "追踪中"), ("paused", "已暂停"), ("ended", "已结束")],
    )
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    overview = models.TextField(blank=True)
    overview_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_scan = models.DateTimeField(null=True)


class Candidate(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="candidates")
    article = models.ForeignKey("news.Article", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default="pending")
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "article"], name="event_article_unique")]


class Node(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="nodes")
    title = models.CharField(max_length=1000)
    summary = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    time_basis = models.CharField(
        max_length=20, default="reported", choices=[("occurred", "事件时间"), ("reported", "报道时间")]
    )
    confirmed = models.BooleanField(default=False)
    edited = models.BooleanField(default=False)
    draft_key = models.CharField(max_length=200, null=True, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at", "-id"]


class NodeReport(models.Model):
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="reports")
    version = models.ForeignKey("news.ArticleVersion", on_delete=models.PROTECT, related_name="event_reports")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["node", "version"], name="node_version_unique")]
