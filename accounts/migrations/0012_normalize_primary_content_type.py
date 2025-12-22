from django.db import migrations


def normalize_primary_content_type(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    UserProfile.objects.filter(primary_content_type="book").update(primary_content_type="audiobook")
    for profile in UserProfile.objects.exclude(interests__isnull=True):
        interests = list(profile.interests or [])
        if "book" not in interests:
            continue
        updated = []
        for value in interests:
            updated.append("audiobook" if value == "book" else value)
        deduped = []
        for value in updated:
            if value not in deduped:
                deduped.append(value)
        profile.interests = deduped
        profile.save(update_fields=["interests"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_alter_userprofile_primary_content_type"),
    ]

    operations = [
        migrations.RunPython(normalize_primary_content_type, migrations.RunPython.noop),
    ]
