from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    """Auto-create UserProfile whenever a User is created.

    Uses get_or_create (not create) so it's idempotent — safe to call
    multiple times and won't crash if the profile already exists. Gated on
    `created` so this doesn't run a query on every ordinary User.save()
    (login timestamps, etc.), only on the User's first save.

    This was previously duplicated by an identical receiver in
    accounts/models.py — consolidated here since signals belong in
    signals.py, wired via accounts/apps.py::ready().
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
