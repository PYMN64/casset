from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    # This migration previously added book alias fields. The project uses only:
    # music / podcast / audiobook / video
    # Kept as NO-OP to preserve migration graph.
    operations = []
