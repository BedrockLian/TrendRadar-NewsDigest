from django.db import models
from django.utils import timezone


class Briefing(models.Model):
    key = models.CharField(max_length=150, unique=True)
    title = models.CharField(max_length=300)
    start = models.DateTimeField()
    end = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)
    revision = models.PositiveIntegerField(default=1)
    legacy_text = models.TextField(blank=True)
    imported = models.BooleanField(default=False)

    class Meta:
        ordering = ["-end", "-revision"]


class BriefItem(models.Model):
    briefing = models.ForeignKey(Briefing, on_delete=models.CASCADE, related_name="items")
    version = models.ForeignKey("news.ArticleVersion", on_delete=models.PROTECT, related_name="brief_items")
    position = models.PositiveIntegerField()
    title = models.TextField()
    summary = models.TextField()
    source = models.CharField(max_length=200)
    url = models.TextField()
    group_key = models.BigIntegerField(null=True)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["briefing", "version"], name="brief_version_unique")]
