import uuid

from django.db import models
from django.utils import timezone


class SiteSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    briefing_times = models.JSONField(default=list)
    max_items = models.PositiveIntegerField(default=20)
    source_limit = models.PositiveIntegerField(default=2)
    retention_days = models.PositiveIntegerField(default=180)
    ai_model = models.CharField(max_length=100, default="deepseek-flash")
    ai_daily_tokens = models.PositiveIntegerField(default=1400000)
    ai_concurrency = models.PositiveIntegerField(default=1)
    db_budget_gb = models.FloatField(default=16)
    soft_free_gb = models.FloatField(default=8)
    hard_free_gb = models.FloatField(default=6)
    last_schedule = models.DateTimeField(default=timezone.now)
    last_backup = models.DateTimeField(null=True)
    storage = models.JSONField(default=dict)
    paused = models.BooleanField(default=False)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1, defaults={"briefing_times": ["08:00", "12:30", "20:00"]})[0]


class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=240, unique=True)
    queue = models.CharField(max_length=20, db_index=True)
    kind = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="pending")
    priority = models.IntegerField(default=100)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    owner = models.UUIDField(null=True)
    result = models.JSONField(default=dict)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True)
    articles = models.ManyToManyField("news.Article", blank=True)

    class Meta:
        indexes = [models.Index(fields=["queue", "status", "available_at", "priority"])]


class ImportMap(models.Model):
    key = models.CharField(max_length=300, unique=True)
    article = models.ForeignKey("news.Article", null=True, on_delete=models.SET_NULL)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class ImportRun(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    source = models.TextField()
    report = models.JSONField(default=dict)


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    since = models.DateTimeField(default=timezone.now)
