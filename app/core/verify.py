import platform
import time
from django.db import connection
from django.test import Client
from django.contrib.auth import get_user_model
from app.news.models import Article, ArticleVersion
from app.briefs.models import Briefing


def verify(ai=False):
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        pg = cursor.fetchone()[0]
    user = get_user_model().objects.filter(is_superuser=True).first()
    if not user:
        raise RuntimeError("管理员不存在")
    client = Client(HTTP_HOST="127.0.0.1", HTTP_X_FORWARDED_PROTO="https")
    client.force_login(user)
    results = {
        "python": platform.python_version(),
        "postgres": pg,
        "articles": Article.objects.count(),
        "versions": ArticleVersion.objects.count(),
        "briefings": Briefing.objects.count(),
        "chinese_versions": ArticleVersion.objects.exclude(title_zh="").count(),
        "pages": {},
    }
    for route in ("/", "/news/", "/briefs/", "/events/", "/dashboard/", "/settings/", "/api/v1/news/"):
        start = time.perf_counter()
        response = client.get(route)
        if response.status_code != 200:
            raise RuntimeError(f"页面验证失败: {route} {response.status_code}")
        results["pages"][route] = {
            "status": response.status_code,
            "ms": round((time.perf_counter() - start) * 1000, 1),
        }
    if ai:
        from app.ai.services import response_call, Enrichment

        response = response_call(
            "将新闻改写为中文标题和简短简介。",
            "A new public library opened today, offering free access to science books.",
            schema=Enrichment,
        )
        Enrichment.model_validate_json(response.output_text)
        results["responses_api"] = {
            "status": response.status,
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    return results
