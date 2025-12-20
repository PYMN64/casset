from django.db import migrations, models
import django.db.models.deletion


def migrate_audiobook_to_book(apps, schema_editor):
    Track = apps.get_model("tracks", "Track")
    Album = apps.get_model("tracks", "Album")
    # Convert old content_type 'audiobook' into 'book' and mark format
    Track.objects.filter(content_type="audiobook").update(content_type="book", book_format="audiobook")
    Album.objects.filter(content_type="audiobook").update(content_type="book")


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
                choices=[("music", "Music"), ("podcast", "Podcast"), ("book", "Book"), ("video", "Video")],
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

        # Track: book format + credits
        migrations.AddField(
            model_name="track",
            name="book_format",
            field=models.CharField(
                choices=[("text", "Text"), ("audiobook", "Audiobook")],
                default="text",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="track",
            name="author_name",
            field=models.CharField(blank=True, max_length=140),
        ),
        migrations.AddField(
            model_name="track",
            name="translator_name",
            field=models.CharField(blank=True, max_length=140),
        ),
        migrations.RunPython(migrate_audiobook_to_book, migrations.RunPython.noop),
    ]
