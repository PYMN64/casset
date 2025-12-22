from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0013_normalize_book_to_audiobook"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="author_name",
            field=models.CharField(blank=True, default="", max_length=140),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="track",
            name="translator_name",
            field=models.CharField(blank=True, default="", max_length=140),
            preserve_default=False,
        ),
    ]
