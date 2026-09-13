import pytest
from app.news.models import Feed, Category
from app.core.models import SiteSettings


@pytest.fixture
def config(db):
    return SiteSettings.current()


@pytest.fixture
def feed(db):
    category = Category.objects.create(slug="tech", name="科技", quota=6)
    return Feed.objects.create(
        slug="test", name="测试新闻源", url="https://example.org/rss", category=category
    )


@pytest.fixture
def item():
    return {
        "url": "https://example.org/news/1?utm_source=rss",
        "guid": "news1",
        "title": "人工智能芯片发布",
        "summary": "新一代人工智能芯片提高计算效率。",
    }


@pytest.fixture
def reader(client, django_user_model, db):
    user = django_user_model.objects.create_user(username="tester", password="test-reader-passphrase-9281")
    client.force_login(user)
    return client
