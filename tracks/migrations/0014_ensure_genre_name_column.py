from django.db import migrations, models


def ensure_genre_name(apps, schema_editor):
    connection = schema_editor.connection
    table_name = apps.get_model("tracks", "Genre")._meta.db_table
    with connection.cursor() as cursor:
        columns = {
            col.name
            for col in connection.introspection.get_table_description(cursor, table_name)
        }
    Genre = apps.get_model("tracks", "Genre")

    if "name" not in columns:
        field = models.CharField(max_length=64, null=True, blank=True)
        field.set_attributes_from_name("name")
        schema_editor.add_field(Genre, field)

    # Backfill missing/blank names from name_fa
    for genre in Genre.objects.filter(models.Q(name__isnull=True) | models.Q(name="")):
        genre.name = genre.name_fa or ""
        genre.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0013_restore_genre_name_field"),
    ]

    operations = [
        migrations.RunPython(ensure_genre_name, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="genre",
            name="name",
            field=models.CharField(max_length=64, blank=True),
        ),
    ]
