from __future__ import annotations

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q

from plays.models import PlayEvent, DailyTrackStat


class Command(BaseCommand):
    help = "Aggregate PlayEvent into DailyTrackStat for a given date (default: yesterday)."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="YYYY-MM-DD")

    def handle(self, *args, **options):
        datestr = (options.get("date") or "").strip()
        if datestr:
            try:
                day = datetime.strptime(datestr, "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("Invalid --date, expected YYYY-MM-DD")
        else:
            day = date.today().fromordinal(date.today().toordinal() - 1)

        day_key = day.isoformat()

        qs = (
            PlayEvent.objects.filter(day_key=day_key)
            .values("track_id")
            .annotate(
                plays=Count("id"),
                unique_plays=Count("ip_hash", distinct=True),
                points_awarded=Count("id", filter=Q(user__isnull=False)),
            )
        )

        with transaction.atomic():
            for row in qs:
                DailyTrackStat.objects.update_or_create(
                    track_id=row["track_id"],
                    day=day,
                    defaults={
                        "plays": row["plays"],
                        "unique_plays": row["unique_plays"],
                        "points_awarded": row["points_awarded"],
                    },
                )

        self.stdout.write(self.style.SUCCESS(f"Aggregated stats for {day_key}"))
