import sqlite3
from app.news.importer import import_legacy
from app.news.models import Article


def test_import_combines_date_and_time_and_repeats_safely(tmp_path, config):
    folder = tmp_path / "output/rss"
    folder.mkdir(parents=True)
    database = folder / "2026-08-01.db"
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE rss_items (id integer,title text,feed_id text,url text,guid text,summary text,first_crawl_time text)"
        )
        db.execute(
            "INSERT INTO rss_items VALUES (1,?,?,?,?,?,?)",
            ("历史报道", "legacy", "https://example.org/old", "old-guid", "存档摘要", "08:30"),
        )
    first = import_legacy(tmp_path)
    second = import_legacy(tmp_path)
    article = Article.objects.get()
    assert article.first_seen.isoformat().startswith("2026-08-01T00:30")
    assert first["added"] == 1 and second["added"] == 0
    assert article.versions.count() == 1
