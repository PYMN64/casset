from django.db import migrations


def normalize_book_to_audiobook(apps, schema_editor):
    Track = apps.get_model("tracks", "Track")
    Album = apps.get_model("tracks", "Album")
    Genre = apps.get_model("tracks", "Genre")
    Track.objects.filter(content_type="book").update(content_type="audiobook")
    Album.objects.filter(content_type="book").update(content_type="audiobook")
    Genre.objects.filter(content_type="book").update(content_type="audiobook")


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0012_merge_20251221_1528"),
    ]

    operations = [
        migrations.RunPython(normalize_book_to_audiobook, migrations.RunPython.noop),
    ]
