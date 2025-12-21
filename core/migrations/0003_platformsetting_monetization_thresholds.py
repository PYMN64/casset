from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_platformsetting_v3_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformsetting",
            name="min_payout_amount",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="platformsetting",
            name="min_payout_points_30d",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="platformsetting",
            name="min_valid_plays_30d",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
