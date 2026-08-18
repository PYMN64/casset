from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


User = get_user_model()


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    """Auto-create UserProfile whenever a User is saved.

    Uses get_or_create (not create) so it's idempotent — safe to call
    multiple times and won't crash if the profile already exists.
    """
    UserProfile.objects.get_or_create(user=instance)
