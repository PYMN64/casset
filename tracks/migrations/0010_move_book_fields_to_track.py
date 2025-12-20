from django.db import migrations, models


class Migration(migrations.Migration):

    # This migration was superseded by 0010_alter_genre_options_remove_track_author_name_and_more
    # and later migrations. It is intentionally kept as a no-op to keep the
    # migration graph consistent without trying to remove non-existent fields.
    dependencies = [
        ("tracks", "0011_remove_genre_author_name_and_more"),
    ]

    operations = []
