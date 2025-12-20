from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_phone_onboarding_and_otp"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="public_handle",
            field=models.SlugField(blank=True, max_length=30, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="public_handle_set_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
