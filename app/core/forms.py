import re
from django import forms
from app.news.models import Feed
from app.news.services import public_url
from app.events.models import Event
from .models import SiteSettings


class FeedForm(forms.ModelForm):
    class Meta:
        model = Feed
        fields = ["slug", "name", "url", "category", "enabled", "interval_seconds"]
        labels = {
            "slug": "来源标识",
            "name": "来源名称",
            "url": "RSS地址",
            "category": "分类",
            "enabled": "启用",
            "interval_seconds": "采集间隔（秒）",
        }

    def clean_url(self):
        return public_url(self.cleaned_data["url"])

    def clean_interval_seconds(self):
        value = self.cleaned_data["interval_seconds"]
        if not 120 <= value <= 86400:
            raise forms.ValidationError("采集间隔应为120至86400秒")
        return value


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "description", "keywords", "status", "start", "end"]
        labels = {
            "name": "事件名称",
            "description": "关注内容",
            "keywords": "关键词与别名",
            "status": "状态",
            "start": "追踪起点",
            "end": "追踪终点",
        }
        widgets = {
            "start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] >= data["end"]:
            raise forms.ValidationError("结束时间应晚于开始时间")
        return data


class SettingsForm(forms.ModelForm):
    times = forms.CharField(label="简报时间", help_text="逗号分隔，例如08:00,12:30,20:00")

    class Meta:
        model = SiteSettings
        fields = [
            "times",
            "max_items",
            "source_limit",
            "retention_days",
            "ai_model",
            "ai_daily_tokens",
            "ai_concurrency",
        ]
        labels = {
            "max_items": "每期最多新闻数",
            "source_limit": "单来源最多条数",
            "retention_days": "普通新闻最长保留天数",
            "ai_model": "AI模型",
            "ai_daily_tokens": "每日AI用量上限",
            "ai_concurrency": "AI同时处理数",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["times"].initial = ",".join(self.instance.briefing_times)

    def clean_times(self):
        slots = sorted(set(s.strip() for s in self.cleaned_data["times"].split(",")))
        if not 1 <= len(slots) <= 8 or any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", s) for s in slots):
            raise forms.ValidationError("请填写1至8个有效的24小时时间")
        return slots

    def clean(self):
        data = super().clean()
        limits = {
            "max_items": (1, 100),
            "source_limit": (1, 20),
            "retention_days": (3, 3650),
            "ai_concurrency": (1, 4),
            "ai_daily_tokens": (0, 10000000),
        }
        for key, (low, high) in limits.items():
            if key in data and not low <= data[key] <= high:
                self.add_error(key, f"范围应为{low}至{high}")
        return data

    def save(self, commit=True):
        self.instance.briefing_times = self.cleaned_data["times"]
        return super().save(commit)
