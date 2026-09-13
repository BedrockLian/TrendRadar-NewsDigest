import time
from django.db import connection


def run(count, confirmed):
    if not confirmed or not connection.settings_dict["NAME"].endswith("_benchmark"):
        raise ValueError("压测只能在名称以_benchmark结尾的独立数据库运行")
    from app.news.models import Feed

    feed, _ = Feed.objects.get_or_create(
        slug="benchmark",
        defaults={"name": "压测来源", "url": "https://benchmark.invalid/rss", "enabled": False},
    )
    start = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("SET statement_timeout = 0")
        cursor.execute(
            """INSERT INTO news_article (url,url_hash,feed_id,first_seen,updated_at,published_at,breaking,imported,search_vector)
            SELECT 'https://benchmark.invalid/'||g, md5(g::text)||md5('b'||g), %s,
            now() - g*interval '1 minute',now()-g*interval '1 minute',now()-g*interval '1 minute',false,true,
            to_tsvector('simple','人工 智能 芯片 technology benchmark '||g)
            FROM generate_series(1,%s) g ON CONFLICT DO NOTHING""",
            [feed.pk, count],
        )
        cursor.execute("SELECT min(id),max(id) FROM news_article WHERE feed_id=%s", [feed.pk])
        first_id, last_id = cursor.fetchone()
        for lower in range(first_id, last_id + 1, 5000):
            upper = lower + 5000
            cursor.execute(
                """INSERT INTO news_articleversion (article_id,fingerprint,title,summary,content,author,title_zh,summary_zh,created_at,meaningful)
            SELECT id,md5(id::text)||md5('v'||id),'人工智能与芯片进展 '||id,
            repeat('用于验证检索分页和容量清理的合成新闻。',20),'','','','',first_seen,true
            FROM news_article WHERE feed_id=%s AND id >= %s AND id < %s ON CONFLICT DO NOTHING""",
                [feed.pk, lower, upper],
            )
            cursor.execute(
                "UPDATE news_article a SET current_id=v.id FROM news_articleversion v WHERE v.article_id=a.id AND a.feed_id=%s AND a.id >= %s AND a.id < %s AND a.current_id IS NULL",
                [feed.pk, lower, upper],
            )
        cursor.execute("ANALYZE news_article")
        cursor.execute("SET statement_timeout = '30s'")
    ingest_seconds = time.perf_counter() - start
    results = {}
    queries = {
        "first_page": "SELECT id FROM news_article ORDER BY first_seen DESC,id DESC LIMIT 40",
        "deep_cursor": "SELECT id FROM news_article WHERE first_seen < now()-interval '100 days' ORDER BY first_seen DESC,id DESC LIMIT 40",
        "search": "SELECT id FROM news_article WHERE search_vector @@ plainto_tsquery('simple','technology') ORDER BY first_seen DESC,id DESC LIMIT 40",
    }
    with connection.cursor() as cursor:
        for key, query in queries.items():
            samples = []
            for _ in range(20):
                t = time.perf_counter()
                cursor.execute(query)
                cursor.fetchall()
                samples.append((time.perf_counter() - t) * 1000)
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query)
            results[key] = {"p95_ms": round(sorted(samples)[18], 2), "plan": cursor.fetchone()[0]}
        cursor.execute("SELECT pg_database_size(current_database())")
        size = cursor.fetchone()[0]
    return {
        "articles": count,
        "load_seconds": round(ingest_seconds, 2),
        "database_bytes": size,
        "queries": results,
    }
