"""core/test_utils.py — Shared helpers for all app test suites.

Why this exists
---------------
`OnboardingRequiredMiddleware` gates every page behind a completed profile.
A user created with plain `User.objects.create_user()` has
`onboarding_complete=False`, so every request in a test gets redirected (302)
and assertions on 200/400/405 fail for reasons unrelated to what is being
tested.

Always build test users through `make_user()` here so this never happens again.
"""

from django.contrib.auth import get_user_model

User = get_user_model()

DEFAULT_PASSWORD = "pass12345"


def make_user(username, *, password=DEFAULT_PASSWORD, onboarded=True, **extra):
    """Create a test user whose profile is ready for normal requests.

    The UserProfile is auto-created by the post_save signal in
    accounts.signals; we only flip `onboarding_complete` so the
    onboarding middleware lets requests through.

    Pass onboarded=False when the test is specifically about the
    onboarding gate itself.
    """
    user = User.objects.create_user(username=username, password=password, **extra)
    if onboarded:
        profile = user.profile
        profile.onboarding_complete = True
        profile.save(update_fields=["onboarding_complete"])
    return user


_PHONE_SEQ = [0]


def make_publisher(username, *, handle=None, **kwargs):
    """Create a user who is allowed to publish.

    Publishing requires a verified phone number and a public handle
    (accounts.models.UserProfile.can_publish, enforced in
    uploads.views.submit_track). Tests about publishing should build their
    creator through this helper rather than re-deriving the requirements —
    when the rule changes, it changes in one place.

    Phone numbers are unique on UserProfile, so each call gets its own.
    """
    from django.utils import timezone

    user = make_user(username, **kwargs)
    profile = user.profile
    _PHONE_SEQ[0] += 1
    profile.phone_number = f"0912{_PHONE_SEQ[0]:07d}"
    profile.phone_verified_at = timezone.now()
    profile.public_handle = handle or f"h-{_PHONE_SEQ[0]}"
    profile.creator_enabled = True
    profile.creator_status = profile.CreatorStatus.APPROVED
    profile.save(update_fields=[
        "phone_number", "phone_verified_at", "public_handle",
        "creator_enabled", "creator_status",
    ])
    return user


def make_superuser(username="test_admin", *, password=DEFAULT_PASSWORD, email="admin@example.com"):
    """Create an onboarded superuser for admin-facing tests."""
    user = User.objects.create_superuser(
        username=username, password=password, email=email
    )
    profile = user.profile
    profile.onboarding_complete = True
    profile.save(update_fields=["onboarding_complete"])
    return user


def login(client, user, password=DEFAULT_PASSWORD):
    """Log a test client in as `user`. Returns True on success."""
    return client.login(username=user.username, password=password)
