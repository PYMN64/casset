from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("plays", "0004_restore_dailytrackstat"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tracks", "0007_restore_tag_and_track_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="FraudFlag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("flag_type", models.CharField(choices=[("play_burst", "Play burst"), ("repeated_ip", "Repeated IP"), ("other", "Other")], max_length=32)),
                ("score", models.PositiveIntegerField(default=1)),
                ("note", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("track", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="fraud_flags", to="tracks.track")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="fraudflag",
            index=models.Index(fields=["flag_type", "created_at"], name="plays_fraud_flag_type_created"),
        ),
    ]
