from __future__ import annotations

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from plays.services import aggregate_daily_stats


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

        written = aggregate_daily_stats(day)
        self.stdout.write(self.style.SUCCESS(f"Aggregated stats for {day.isoformat()} ({written} tracks)"))
