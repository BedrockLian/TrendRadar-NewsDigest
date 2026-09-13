from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone


class Category(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    quota = models.PositiveIntegerField(default=3)
    weight = models.FloatField(default=1)

    def __str__(self):
        return self.name


class Feed(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=2048, unique=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    enabled = models.BooleanField(default=True)
    interval_seconds = models.PositiveIntegerField(default=600)
    boost_until = models.DateTimeField(null=True, blank=True)
    next_fetch = models.DateTimeField(default=timezone.now, db_index=True)
    etag = models.TextField(blank=True)
    modified = models.TextField(blank=True)
    failures = models.PositiveIntegerField(default=0)
    last_success = models.DateTimeField(null=True)
    last_status = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return self.name

    @property
    def status_label(self):
        if not self.enabled:
            return "已暂停"
        if self.last_status.startswith("not_modified"):
            return "正常 · 暂无更新"
        if self.last_status.startswith("success"):
            return "抓取成功"
        if self.last_status.endswith(":429"):
            return "来源限流"
        if self.last_status.startswith("failed"):
            return "抓取失败"
        return "尚未执行"


class StoryGroup(models.Model):
    title = models.CharField(max_length=1000)
    created_at = models.DateTimeField(default=timezone.now)


class Article(models.Model):
    url = models.TextField()
    url_hash = models.CharField(max_length=64, unique=True)
    feed = models.ForeignKey(Feed, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL)
    group = models.ForeignKey(StoryGroup, null=True, blank=True, on_delete=models.SET_NULL)
    first_seen = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    published_at = models.DateTimeField(null=True)
    current = models.ForeignKey(
        "ArticleVersion", null=True, on_delete=models.SET_NULL, related_name="current_for"
    )
    search_vector = SearchVectorField(null=True)
    breaking = models.BooleanField(default=False)
    imported = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["-first_seen", "-id"]),
            models.Index(fields=["feed", "-first_seen"]),
            models.Index(fields=["category", "-first_seen"]),
            models.Index(fields=["updated_at"]),
            GinIndex(fields=["search_vector"]),
        ]

    @property
    def title(self):
        return self.current.title_zh or self.current.title if self.current else "无标题"


class ArticleVersion(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="versions")
    fingerprint = models.CharField(max_length=64)
    title = models.TextField()
    summary = models.TextField(blank=True)
    content = models.TextField(blank=True)
    author = models.CharField(max_length=500, blank=True)
    title_zh = models.TextField(blank=True)
    summary_zh = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    meaningful = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["article", "fingerprint"], name="version_content_unique")
        ]


class FeedIdentity(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    identity = models.CharField(max_length=64)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="identities")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["feed", "identity"], name="feed_identity_unique")]


class Tombstone(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    expires_at = models.DateTimeField(db_index=True)


class Favourite(models.Model):
    version = models.OneToOneField(ArticleVersion, on_delete=models.PROTECT, related_name="favourite")
    created_at = models.DateTimeField(default=timezone.now)


class CrawlRun(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(default=timezone.now)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    job_key = models.CharField(max_length=240)
    status = models.CharField(max_length=30)
    http_status = models.IntegerField(default=0)
    parsed = models.PositiveIntegerField(default=0)
    added = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    duplicate = models.PositiveIntegerField(default=0)
    elapsed_ms = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)


class HourStat(models.Model):
    hour = models.DateTimeField()
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    requests = models.PositiveIntegerField(default=0)
    successes = models.PositiveIntegerField(default=0)
    parsed = models.PositiveIntegerField(default=0)
    added = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    duplicate = models.PositiveIntegerField(default=0)
    elapsed_ms = models.BigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["hour", "feed"], name="hour_feed_unique")]


class DomainLease(models.Model):
    hostname = models.CharField(max_length=255, primary_key=True)
    until = models.DateTimeField(default=timezone.now)
    owner = models.CharField(max_length=36, blank=True)
