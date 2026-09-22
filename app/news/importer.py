import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import yaml
from django.db import transaction
from django.utils import timezone

from app.briefs.models import Briefing, BriefItem
from app.core.models import ImportMap, ImportRun, SiteSettings

from .models import Category, Feed
from .services import digest, index_article, ingest, timestamp


def inspect_legacy(root):
    root = Path(root)
    state_path = root / "output/briefings/.state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    databases = sorted((root / "output/rss").glob("*.db"))
    counts = {}
    for path in databases:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            try:
                counts[path.name] = db.execute("SELECT count(*) FROM rss_items").fetchone()[0]
            except sqlite3.Error:
                counts[path.name] = 0
    return {
        "state_articles": len(state.get("articles", {})),
        "briefings": len(state.get("results", {})),
        "databases": counts,
        "raw_bytes": sum(p.stat().st_size for p in databases),
        "estimated_upper_bytes": (sum(counts.values()) + len(state.get("articles", {}))) * 30000,
    }


def import_legacy(root, dry_run=False, max_articles=None):
    root = Path(root).resolve()
    report = inspect_legacy(root)
    if dry_run:
        return report
    config_path = root / "config/config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    categories = {}
    for item in config.get("digest", {}).get("categories", []):
        category, _ = Category.objects.get_or_create(
            slug=item["id"],
            defaults={"name": item["name"], "quota": item.get("quota", 3), "weight": item.get("weight", 1)},
        )
        for slug in item.get("feeds", []):
            categories[slug] = category
    feeds = {}
    for item in config.get("rss", {}).get("feeds", []):
        feed, _ = Feed.objects.get_or_create(
            slug=item["id"],
            defaults={
                "name": item.get("name", item["id"]),
                "url": item["url"],
                "enabled": item.get("enabled", True),
                "category": categories.get(item["id"]),
            },
        )
        feeds[feed.slug] = feed
    state_path = root / "output/briefings/.state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    articles = state.get("articles", {})
    cache_path = root / "output/briefings/.translations.json"
    translations = (
        json.loads(cache_path.read_text(encoding="utf-8")).get("entries", {}) if cache_path.exists() else {}
    )
    for item in articles.values():
        cached = translations.get(item.get("content_hash"), {})
        item.update({k: cached[k] for k in ("title_zh", "summary_zh") if cached.get(k)})
    reference_ids = {aid for b in state.get("results", {}).values() for aid in b.get("article_ids", [])}
    outcomes = {
        "articles": 0,
        "added": 0,
        "updated": 0,
        "duplicate": 0,
        "skipped": 0,
        "failed": 0,
        "briefs": 0,
    }
    imported = {}
    failures = []

    def add(old_id, item, protected=False):
        map_key = "legacy:" + str(old_id)
        source_hash = digest(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
        mapping = ImportMap.objects.filter(key=map_key).select_related("article__current").first()
        if mapping and mapping.article and mapping.data.get("source_hash") == source_hash:
            imported[str(old_id)] = mapping.article
            outcomes["duplicate"] += 1
            return mapping.article
        if max_articles and outcomes["articles"] >= max_articles and not protected:
            outcomes["skipped"] += 1
            return None
        if outcomes["articles"] % 200 == 0:
            from app.core.storage import measure

            space = measure()
            cfg = SiteSettings.current()
            if space["free_gb"] < cfg.hard_free_gb or space["database_gb"] >= cfg.db_budget_gb:
                outcomes["skipped"] += 1
                return None
        slug = item.get("feed_id", "legacy")
        feed = feeds.get(slug)
        if not feed:
            feed, _ = Feed.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": item.get("feed_name", slug),
                    "url": "https://legacy.invalid/" + slug,
                    "enabled": False,
                },
            )
            feeds[slug] = feed
        try:
            with transaction.atomic():
                article, outcome = ingest(feed, item, imported=True)
                if article:
                    if item.get("title_zh") and article.current and not article.current.title_zh:
                        article.current.title_zh = item["title_zh"]
                        article.current.summary_zh = item.get("summary_zh", "")
                        article.current.save(update_fields=["title_zh", "summary_zh"])
                        index_article(article)
                    ImportMap.objects.update_or_create(
                        key=map_key, defaults={"article": article, "data": {"source_hash": source_hash}}
                    )
                    imported[str(old_id)] = article
                    outcomes["articles"] += 1
                outcomes[outcome] += 1
                return article
        except (ValueError, KeyError) as exc:
            outcomes["failed"] += 1
            if len(failures) < 100:
                failures.append({"id": str(old_id), "error": type(exc).__name__})

    # Protect historical briefing citations before filling remaining storage with ordinary news.
    for aid in reference_ids:
        if aid in articles:
            add(aid, articles[aid], protected=True)
    for old_key, record in state.get("results", {}).items():
        key = "legacy:" + digest(old_key)
        existing_brief = Briefing.objects.filter(key=key).first()
        if existing_brief:
            for old, new in {
                "历史digest": "历史新闻简报",
                "历史alert": "历史突发简报",
                "历史weekly": "历史周报",
            }.items():
                existing_brief.title = existing_brief.title.replace(old, new)
            existing_brief.save(update_fields=["title"])
            continue
        when = timestamp(record.get("created_at")) or timezone.now()
        text = ""
        raw_path = str(record.get("archive_path", "")).replace("\\", "/")
        if "output/" in raw_path:
            raw_path = raw_path[raw_path.index("output/") :]
        candidate = (root / raw_path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            text = candidate.read_text(encoding="utf-8")[:1000000]
        with transaction.atomic():
            brief = Briefing.objects.create(
                key=key,
                title=f"{timezone.localtime(when):%m月%d日} · 历史{ {'digest': '新闻简报', 'alert': '突发简报', 'weekly': '周报'}.get(record.get('kind'), '新闻简报') }",
                start=when - timedelta(hours=12),
                end=when,
                legacy_text=text,
                imported=True,
            )
            for i, aid in enumerate(record.get("article_ids", []), 1):
                a = imported.get(str(aid))
                if not a or not a.current:
                    continue
                BriefItem.objects.get_or_create(
                    briefing=brief,
                    version=a.current,
                    defaults={
                        "position": i,
                        "title": a.title,
                        "summary": a.current.summary_zh or a.current.summary,
                        "source": a.feed.name,
                        "url": a.url,
                    },
                )
            outcomes["briefs"] += 1
    for aid, item in sorted(articles.items(), key=lambda pair: pair[1].get("first_seen", ""), reverse=True):
        if aid not in reference_ids:
            add(aid, item)
    for path in sorted((root / "output/rss").glob("*.db"), reverse=True):
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            try:
                rows = db.execute("SELECT * FROM rss_items ORDER BY id DESC")
            except sqlite3.Error:
                continue
            for row in rows:
                item = dict(row)
                first = str(item.get("first_crawl_time") or "00:00")
                item["first_seen"] = f"{path.stem}T{first}:00+08:00" if len(first) == 5 else first
                add(f"{path.name}:{item['id']}", item)
    # Preserve readable markdown briefings even when their state entry is missing.
    for path in sorted((root / "output/briefings").rglob("*.md")):
        text = path.read_text(encoding="utf-8")[:1000000]
        if Briefing.objects.filter(legacy_text=text).exists():
            continue
        when = timezone.make_aware(__import__("datetime").datetime.fromtimestamp(path.stat().st_mtime))
        _, created = Briefing.objects.get_or_create(
            key="legacy-file:" + digest(str(path.relative_to(root))),
            defaults={"title": path.stem, "start": when, "end": when, "legacy_text": text, "imported": True},
        )
        outcomes["briefs"] += int(created)
    from .models import Article

    report.update(outcomes)
    report["records_processed"] = report["articles"]
    report["articles"] = Article.objects.count()
    report["failures"] = failures
    ImportRun.objects.create(source=str(root), report=report)
    return report
