from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0002_loginattempt")]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="ai_daily_tokens",
            field=models.PositiveIntegerField(default=500000),
        )
    ]
