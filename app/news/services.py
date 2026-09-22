import hashlib
import html
import ipaddress
import re
import socket
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jieba
from django.core import signing
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags

from .models import Article, ArticleVersion, FeedIdentity, Tombstone


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def plain(value):
    return re.sub(r"\s+", " ", html.unescape(strip_tags(str(value or "")))).strip()


def canonical_url(url):
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
        raise ValueError("仅允许普通 HTTP/HTTPS 地址")
    host = parts.hostname.lower().encode("idna").decode()
    port = parts.port
    if ":" in host:
        host = f"[{host}]"
    if port and port != (443 if parts.scheme == "https" else 80):
        host += f":{port}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
    ]
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(sorted(query)), ""))


def public_url(url):
    value = canonical_url(url)
    parts = urlsplit(value)
    if parts.port and parts.port not in (80, 443):
        raise ValueError("RSS 仅支持 80/443 端口")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("RSS 地址必须指向公网")
    return value


def timestamp(value):
    if not value:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        result = parse_datetime(str(value))
    if result and timezone.is_naive(result):
        result = timezone.make_aware(result)
    return result


def terms(text):
    text = text.casefold()
    tokens = re.findall(r"[a-z0-9]+", text)
    tokens.extend(w for w in jieba.cut(text) if re.fullmatch(r"[\u3400-\u9fff]{2,}", w))
    for span in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.extend(span[i : i + 2] for i in range(len(span) - 1))
    return list(dict.fromkeys(tokens))[:1200]


def index_article(article):
    version = article.current
    if not version:
        return
    title = " ".join(terms(version.title + " " + version.title_zh))
    body = " ".join(terms(version.summary[:1200] + " " + version.summary_zh[:800]))
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE news_article SET search_vector = setweight(to_tsvector('simple', %s),'A') || setweight(to_tsvector('simple', %s),'B') WHERE id=%s",
            [title, body, article.pk],
        )


def enqueue_enrichment(article_id, version_id):
    from django.conf import settings

    if not settings.AI_KEY:
        return
    from app.core.models import SiteSettings
    from app.core.tasks import enqueue

    article = Article.objects.get(pk=article_id)
    config = SiteSettings.current()
    enqueue(
        "enrich",
        f"enrich:{version_id}:{config.ai_model}",
        {"version": version_id},
        queue="ai",
        priority=20 if article.breaking else 30,
        articles=[article],
    )


@transaction.atomic
def ingest(feed, item, *, imported=False):
    url = canonical_url(item["url"])
    key = digest(url)
    identity = digest(str(item.get("guid") or url))
    if Tombstone.objects.filter(
        key__in=[key, digest(f"{feed.pk}:{identity}")], expires_at__gt=timezone.now()
    ).exists():
        return None, "duplicate"
    # Serializes identity creation across feeds without holding a lock during HTTP.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [int(key[:15], 16)])
    mapping = FeedIdentity.objects.select_related("article").filter(feed=feed, identity=identity).first()
    article = mapping.article if mapping else Article.objects.filter(url_hash=key).first()
    created = article is None
    first = timestamp(item.get("first_seen")) if imported else None
    if created:
        article = Article.objects.create(
            url=url,
            url_hash=key,
            feed=feed,
            category=feed.category,
            first_seen=first or timezone.now(),
            published_at=timestamp(item.get("published_at")),
            imported=imported,
        )
    article = Article.objects.select_for_update().get(pk=article.pk)
    if first and first < article.first_seen:
        article.first_seen = first
        article.save(update_fields=["first_seen"])
    FeedIdentity.objects.get_or_create(feed=feed, identity=identity, defaults={"article": article})
    title = plain(item.get("title"))[:4000] or url
    summary = plain(item.get("summary"))[:32000]
    content = plain(item.get("content"))[:256000]
    fingerprint = digest(f"{title}\n{summary}\n{content}")
    version, fresh = ArticleVersion.objects.get_or_create(
        article=article,
        fingerprint=fingerprint,
        defaults={
            "title": title,
            "summary": summary,
            "content": content,
            "author": plain(item.get("author"))[:500],
            "title_zh": plain(item.get("title_zh"))[:4000],
            "summary_zh": plain(item.get("summary_zh"))[:32000],
            "created_at": timestamp(item.get("updated_at")) or first or timezone.now(),
        },
    )
    if fresh:
        old = article.current
        normalize = lambda s: re.sub(r"[^\w]", "", s.casefold())
        version.meaningful = not old or normalize(old.title + old.summary + old.content) != normalize(
            title + summary + content
        )
        version.save(update_fields=["meaningful"])
        if not imported or not old or version.created_at >= old.created_at:
            article.current = version
            article.updated_at = version.created_at
            article.breaking = not imported and bool(
                re.search(
                    r"突发|地震|海啸|政变|空袭|breaking news|breaking:|earthquake|missile attack",
                    title,
                    re.IGNORECASE,
                )
            )
            article.save(update_fields=["current", "updated_at", "breaking"])
            index_article(article)
    elif not article.current_id:
        article.current = version
        article.save(update_fields=["current"])
        index_article(article)
    if imported and article.imported and first and not fresh and version.created_at > first:
        version.created_at = timestamp(item.get("updated_at")) or first
        version.save(update_fields=["created_at"])
        if article.current_id == version.pk:
            article.updated_at = version.created_at
            article.save(update_fields=["updated_at"])
    if fresh and not imported and article.current_id == version.pk and not version.title_zh:
        transaction.on_commit(
            lambda article_id=article.pk, version_id=version.pk: enqueue_enrichment(article_id, version_id)
        )
    return article, "added" if created else "updated" if fresh else "duplicate"


def search_articles(query="", *, feed=None, category=None, start=None, end=None, cursor=None, limit=40):
    qs = Article.objects.select_related("current", "feed", "category", "group").filter(current__isnull=False)
    if query:
        if len(query.strip()) < 2:
            raise ValueError("请输入至少两个字符")
        tokens = terms(query)
        if not tokens:
            return [], None
        from django.contrib.postgres.search import SearchQuery

        qs = qs.filter(search_vector=SearchQuery(" ".join(tokens), config="simple", search_type="plain"))
    if feed:
        qs = qs.filter(feed_id=feed)
    if category:
        qs = qs.filter(category_id=category)
    if start:
        qs = qs.filter(first_seen__gte=start)
    if end:
        qs = qs.filter(first_seen__lt=end)
    if cursor:
        data = signing.loads(cursor, salt="news.cursor", max_age=86400 * 30)
        when = timestamp(data[0])
        qs = qs.filter(Q(first_seen__lt=when) | Q(first_seen=when, id__lt=data[1]))
    rows = list(qs.order_by("-first_seen", "-id")[: limit + 1])
    next_cursor = (
        signing.dumps([rows[limit - 1].first_seen.isoformat(), rows[limit - 1].pk], salt="news.cursor")
        if len(rows) > limit
        else None
    )
    return rows[:limit], next_cursor


def article_dict(article):
    v = article.current
    return {
        "id": article.pk,
        "version_id": v.pk,
        "title": v.title_zh or v.title,
        "original_title": v.title,
        "summary": v.summary_zh or v.summary,
        "url": article.url,
        "source": article.feed.name,
        "first_seen": article.first_seen.isoformat(),
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "group": article.group_id,
        "breaking": article.breaking,
    }
