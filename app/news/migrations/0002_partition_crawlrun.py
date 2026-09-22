from django.db import migrations

SQL = """
ALTER TABLE news_crawlrun RENAME TO news_crawlrun_old;
CREATE TABLE news_crawlrun (LIKE news_crawlrun_old INCLUDING DEFAULTS INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE) PARTITION BY RANGE (created_at);
ALTER TABLE news_crawlrun ADD PRIMARY KEY (id, created_at);
ALTER TABLE news_crawlrun ADD FOREIGN KEY (feed_id) REFERENCES news_feed(id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX news_crawlrun_feed_time ON news_crawlrun (feed_id, created_at DESC);
CREATE TABLE news_crawlrun_default PARTITION OF news_crawlrun DEFAULT;
INSERT INTO news_crawlrun OVERRIDING SYSTEM VALUE SELECT * FROM news_crawlrun_old;
SELECT setval(pg_get_serial_sequence('news_crawlrun','id'), GREATEST(COALESCE((SELECT max(id) FROM news_crawlrun),0),1), EXISTS(SELECT 1 FROM news_crawlrun));
DROP TABLE news_crawlrun_old;
"""


class Migration(migrations.Migration):
    dependencies = [("news", "0001_initial")]
    operations = [migrations.RunSQL(SQL)]
