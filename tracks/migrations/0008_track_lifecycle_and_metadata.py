from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("tracks", "0007_restore_tag_and_track_tags"),]

    operations = [
        migrations.AddField(
            model_name="track",
            name="language",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="track",
            name="explicit",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="track",
            name="visibility",
            field=models.CharField(
                choices=[("public", "Public"), ("unlisted", "Unlisted"), ("private", "Private")],
                default="private",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="track",
            name="submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="track",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="track",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="track",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("takedown", "Takedown"),
                    ("blocked", "Blocked"),
                    ("pending", "Pending (legacy)"),
                ],
                default="draft",
                max_length=16,
            ),
        ),
    ]
