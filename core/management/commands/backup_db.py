"""Management command: backup_db

Wraps `pg_dump` to write a timestamped, compressed backup of the production
database. Only meaningful when DB_ENGINE=postgresql (Constitution, CLAUDE.md
§2: production must run PostgreSQL) — refuses to run against SQLite, where a
raw file copy of db.sqlite3 is the appropriate backup, not this command.

Usage
-----
    python manage.py backup_db                       # writes to ./backups/
    python manage.py backup_db --output-dir /var/backups/casset

Recommended cron (documented in full at .casset/ops/backup.md):
    0 3 * * *  cd /path/to/casset && DJANGO_SETTINGS_MODULE=config.settings.prod \
               python manage.py backup_db --output-dir /var/backups/casset
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger("casset.core")


class Command(BaseCommand):
    help = "Back up the PostgreSQL database with pg_dump (production only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=str,
            default="backups",
            help="Directory to write the dump file into (created if missing).",
        )

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError(
                "backup_db only supports PostgreSQL (DB_ENGINE=postgresql). "
                "For SQLite, back up the db.sqlite3 file directly."
            )

        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = output_dir / f"casset_{timestamp}.dump"

        cmd = [
            "pg_dump",
            f"--host={db['HOST']}",
            f"--port={db['PORT']}",
            f"--username={db['USER']}",
            "--format=custom",
            f"--file={dest}",
            db["NAME"],
        ]
        env = {**os.environ, "PGPASSWORD": db.get("PASSWORD", "")}

        self.stdout.write(f"Running pg_dump -> {dest}")
        try:
            subprocess.run(  # noqa: S603 — args are settings-derived, not user input
                cmd, env=env, check=True, capture_output=True, text=True,
            )
        except FileNotFoundError as exc:
            raise CommandError(
                "pg_dump was not found on PATH. Install the PostgreSQL client tools."
            ) from exc
        except subprocess.CalledProcessError as exc:
            logger.error("pg_dump failed: %s", exc.stderr)
            raise CommandError(f"pg_dump failed: {exc.stderr}") from exc

        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info("backup_db: wrote %s (%.1f MB)", dest, size_mb)
        self.stdout.write(self.style.SUCCESS(f"Backup written: {dest} ({size_mb:.1f} MB)"))
