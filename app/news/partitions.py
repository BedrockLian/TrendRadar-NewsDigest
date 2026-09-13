from datetime import datetime, timedelta, timezone
from django.db import connection, transaction
from psycopg import sql


def ensure_partitions():
    now = datetime.now(timezone.utc)
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(7142302)")
        for offset in (0, 1, 2):
            start = month
            for _ in range(offset):
                start = (start + timedelta(days=32)).replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
            name = f"news_crawlrun_{start:%Y%m}"
            cursor.execute("SELECT to_regclass(%s)", [name])
            if cursor.fetchone()[0]:
                continue
            # Move rows from the catch-all partition atomically before attaching the monthly partition.
            cursor.execute("LOCK TABLE news_crawlrun IN ACCESS EXCLUSIVE MODE")
            cursor.execute(
                sql.SQL(
                    "CREATE TABLE {} (LIKE news_crawlrun INCLUDING DEFAULTS INCLUDING GENERATED INCLUDING STORAGE)"
                ).format(sql.Identifier(name))
            )
            cursor.execute(
                sql.SQL(
                    "WITH moved AS (DELETE FROM news_crawlrun_default WHERE created_at >= %s AND created_at < %s RETURNING *) INSERT INTO {} SELECT * FROM moved"
                ).format(sql.Identifier(name)),
                [start, end],
            )
            cursor.execute(
                sql.SQL("ALTER TABLE news_crawlrun ATTACH PARTITION {} FOR VALUES FROM ({}) TO ({})").format(
                    sql.Identifier(name), sql.Literal(start), sql.Literal(end)
                )
            )
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename ~ '^news_crawlrun_[0-9]{6}$'"
        )
        for (name,) in cursor.fetchall():
            start = datetime.strptime(name[-6:], "%Y%m").replace(tzinfo=timezone.utc)
            end = (start + timedelta(days=32)).replace(day=1)
            if end < now - timedelta(days=14):
                cursor.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(name)))
