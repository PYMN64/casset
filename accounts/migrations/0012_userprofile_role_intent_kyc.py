from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_alter_userprofile_primary_content_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="role_intent",
            field=models.CharField(
                choices=[("viewer", "Viewer"), ("creator", "Creator")],
                default="viewer",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="legal_full_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="national_id",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="bank_iban",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
