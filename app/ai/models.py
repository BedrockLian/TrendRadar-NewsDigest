from django.db import models
from django.utils import timezone


class UsageDay(models.Model):
    day = models.DateField(primary_key=True)
    used = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(default=0)
    estimated = models.PositiveIntegerField(default=0)
    lane_used = models.JSONField(default=dict)
    lane_reserved = models.JSONField(default=dict)


class Generation(models.Model):
    key = models.CharField(max_length=64, unique=True)
    capability = models.CharField(max_length=40)
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=20, default="1")
    version = models.ForeignKey("news.ArticleVersion", null=True, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default="pending")
    output = models.JSONField(default=dict)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    error = models.CharField(max_length=200, blank=True)


class Conversation(models.Model):
    title = models.CharField(max_length=300)
    created_at = models.DateTimeField(default=timezone.now)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20)
    text = models.TextField()
    evidence = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="completed")
    created_at = models.DateTimeField(default=timezone.now)
