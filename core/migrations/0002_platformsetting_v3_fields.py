from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsetting',
            name='enable_book',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='playback_point_percent',
            field=models.PositiveIntegerField(default=60, help_text='Percent of playback required to award 1 point (e.g. 60)'),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='price_per_point_book',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
