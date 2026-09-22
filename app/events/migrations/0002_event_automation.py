import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="event",
            name="auto_managed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="event",
            name="lifecycle_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="event",
            name="last_reviewed_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.CreateModel(
            name="EventReview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("selected", "已选入事件"), ("excluded", "不构成重大事件")],
                        max_length=20,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                (
                    "reviewed_at",
                    models.DateTimeField(default=django.utils.timezone.now, db_index=True),
                ),
                (
                    "article",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_review",
                        to="news.article",
                    ),
                ),
            ],
        ),
    ]
