from django.db import migrations


def normalize_audiobook_genre_slugs(apps, schema_editor):
    Genre = apps.get_model("tracks", "Genre")
    slug_map = {
        "business-book": "business-audiobook",
        "education-book": "education-audiobook",
        "psychology-book": "psychology-audiobook",
    }
    for old_slug, new_slug in slug_map.items():
        Genre.objects.filter(slug=old_slug).update(slug=new_slug)


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0014_add_audiobook_credits"),
    ]

    operations = [
        migrations.RunPython(normalize_audiobook_genre_slugs, migrations.RunPython.noop),
    ]
