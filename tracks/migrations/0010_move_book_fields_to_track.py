from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracks", "0009_genre_per_content_and_book_format"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="genre",
            name="book_format",
        ),
        migrations.RemoveField(
            model_name="genre",
            name="author_name",
        ),
        migrations.RemoveField(
            model_name="genre",
            name="translator_name",
        ),
        migrations.AddField(
            model_name="track",
            name="book_format",
            field=models.CharField(choices=[("text", "Text"), ("audiobook", "Audiobook")], default="text", max_length=16),
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
    ]
