# Generated manually for Genre v2 upgrade
from django.db import migrations, models


def forwards(apps, schema_editor):
    Genre = apps.get_model("tracks", "Genre")
    order = 0
    for genre in Genre.objects.all().order_by("pk"):
        order += 10
        if not genre.content_type:
            genre.content_type = "music"
        if not genre.name_fa:
            genre.name_fa = genre.name or ""
        if not genre.name_en:
            genre.name_en = ""
        if not genre.order:
            genre.order = order
        if genre.is_active is None:
            genre.is_active = True
        genre.save(update_fields=[
            "content_type",
            "name_fa",
            "name_en",
            "order",
            "is_active",
        ])


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0011_remove_genre_author_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="genre",
            name="content_type",
            field=models.CharField(choices=[("music", "Music"), ("podcast", "Podcast"), ("audiobook", "Audiobook"), ("video", "Video")], default="music", max_length=16),
        ),
        migrations.AddField(
            model_name="genre",
            name="name_fa",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="genre",
            name="name_en",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="genre",
            name="parent",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="children", to="tracks.genre"),
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
        migrations.AlterModelOptions(
            name="genre",
            options={"ordering": ["content_type", "order", "name_fa"]},
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
