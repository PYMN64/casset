from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0008_track_lifecycle_and_metadata"),
    ]

    operations = [
        # Genre: rename name -> name_fa, add content_type + extras
        migrations.RenameField(
            model_name="genre",
            old_name="name",
            new_name="name_fa",
        ),
        migrations.AddField(
            model_name="genre",
            name="content_type",
            field=models.CharField(
                choices=[
                    ("music", "Music"),
                    ("podcast", "Podcast"),
                    ("audiobook", "Audiobook"),
                    ("video", "Video"),
                ],
                default="music",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="genre",
            name="name_en",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="genre",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="children",
                to="tracks.genre",
            ),
        ),
        migrations.AddField(
            model_name="genre",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="genre",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
