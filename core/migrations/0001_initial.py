# Generated manually for portability (migration-safe).

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='PlatformSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enable_music', models.BooleanField(default=True)),
                ('enable_podcast', models.BooleanField(default=True)),
                ('enable_audiobook', models.BooleanField(default=False)),
                ('enable_video', models.BooleanField(default=False)),
                ('free_upload_minutes', models.PositiveIntegerField(default=180)),
                ('creator_daily_upload_limit', models.PositiveIntegerField(default=20)),
                ('play_award_percent', models.FloatField(default=0.6)),
                ('price_per_point_music', models.PositiveIntegerField(default=0)),
                ('price_per_point_podcast', models.PositiveIntegerField(default=0)),
                ('price_per_point_audiobook', models.PositiveIntegerField(default=0)),
                ('price_per_point_video', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Platform setting',
                'verbose_name_plural': 'Platform settings',
            },
        ),
    ]
