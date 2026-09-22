from django.db import migrations, models


def raise_quota(apps, schema_editor):
    settings = apps.get_model("core", "SiteSettings")
    settings.objects.filter(ai_daily_tokens__lte=500000).update(ai_daily_tokens=1000000)


class Migration(migrations.Migration):
    dependencies = [("core", "0003_alter_sitesettings_ai_daily_tokens")]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="ai_daily_tokens",
            field=models.PositiveIntegerField(default=1000000),
        ),
        migrations.RunPython(raise_quota, migrations.RunPython.noop),
    ]
