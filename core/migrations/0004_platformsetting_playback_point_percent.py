from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_platformsetting_monetization_thresholds"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsetting",
            name="playback_point_percent",
            field=models.PositiveIntegerField(
                default=60,
                help_text="Percent of playback required to award 1 point (e.g. 60)",
            ),
        ),
    ]
