from django.db import migrations, models


def backfill_localized_snapshots(apps, schema_editor):
    brief_item = apps.get_model("briefs", "BriefItem")
    for item in brief_item.objects.select_related("version").iterator(chunk_size=500):
        changes = {}
        if item.version.title_zh:
            changes["title_zh"] = item.version.title_zh
        if item.version.summary_zh:
            changes["summary_zh"] = item.version.summary_zh
        if changes:
            brief_item.objects.filter(pk=item.pk).update(**changes)


class Migration(migrations.Migration):
    dependencies = [("briefs", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="briefitem",
            name="title_zh",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="briefitem",
            name="summary_zh",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(backfill_localized_snapshots, migrations.RunPython.noop),
    ]
