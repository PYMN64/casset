"""Management command: recalculate_points

Rebuilds UserProfile.points from PointLedger for all users (or a subset).
Use this whenever you suspect drift between the cache field and the ledger.

Usage
-----
    # Dry-run: show what would change, touch nothing
    python manage.py recalculate_points --dry-run

    # Fix everyone
    python manage.py recalculate_points

    # Fix one user
    python manage.py recalculate_points --user-id 42
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from accounts.models import UserProfile
from plays.models import PointLedger

User = get_user_model()
logger = logging.getLogger("casset.plays")


class Command(BaseCommand):
    help = "Rebuild UserProfile.points from PointLedger (source of truth)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show discrepancies without making any changes.",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Recalculate only for this user ID.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        user_id = options["user_id"]

        profiles = UserProfile.objects.select_related("user")
        if user_id:
            profiles = profiles.filter(user_id=user_id)

        total = profiles.count()
        fixed = 0
        ok = 0

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Recalculating points for {total} profile(s)"
                + (" [DRY RUN]" if dry_run else "")
            )
        )

        for profile in profiles.iterator():
            canonical = (
                PointLedger.objects
                .filter(user=profile.user)
                .aggregate(total=Sum("delta"))["total"]
            ) or 0

            if canonical == profile.points:
                ok += 1
                continue

            diff = canonical - profile.points
            sign = "+" if diff > 0 else ""
            msg = (
                f"  user={profile.user.username} (id={profile.user_id}) | "
                f"ledger={canonical} cache={profile.points} diff={sign}{diff}"
            )

            if dry_run:
                self.stdout.write(self.style.WARNING(msg))
            else:
                with transaction.atomic():
                    UserProfile.objects.filter(pk=profile.pk).update(points=canonical)
                self.stdout.write(self.style.SUCCESS(msg + " -> FIXED"))
                logger.info(
                    "recalculate_points: user=%s ledger=%d old_cache=%d",
                    profile.user_id, canonical, profile.points,
                )
                fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {ok} already correct, {fixed} fixed"
                + (" (dry-run, no writes)" if dry_run else "") + "."
            )
        )
