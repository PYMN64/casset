from django.db import migrations, models


def forwards(apps, schema_editor):
    Genre = apps.get_model("tracks", "Genre")
    for genre in Genre.objects.all():
        if genre.name is None or genre.name == "":
            genre.name = genre.name_fa or ""
            genre.save(update_fields=["name"])


def backwards(apps, schema_editor):
    Genre = apps.get_model("tracks", "Genre")
    for genre in Genre.objects.all():
        genre.name = None
        genre.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0012_genre_v2_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="genre",
            name="name",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="genre",
            name="name",
            field=models.CharField(max_length=64, unique=True),
        ),
    ]
