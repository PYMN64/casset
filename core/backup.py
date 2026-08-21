"""core/backup.py — automated database backup, run on a schedule via
core/tasks.py::backup_database_task (config/settings/base.py::
CELERY_BEAT_SCHEDULE).

Deliberately separate from `core/management/commands/backup_db.py`, which
stays a plain local-disk pg_dump wrapper for a manual/cron operator run
(documented in .casset/ops/backup.md) with its own existing test coverage.
This module adds the piece that command never had: uploading the dump to
the project's configured object storage (django-storages S3 in prod, the
same `default_storage` abstraction media files already use — local disk in
dev) so a backup survives the database server's own disk failing, not just
a bad migration.
"""

import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import default_storage

logger = logging.getLogger("casset.core")


class BackupError(Exception):
    """Raised when a backup cannot be produced or stored — never swallowed,
    so a scheduled run that fails shows up as a real Celery task failure
    (and in Sentry, when configured) instead of silently doing nothing."""


def run_database_backup(*, upload: bool = True) -> dict:
    """Run `pg_dump` and, unless *upload* is False, save the result to the
    project's configured object storage under `backups/`.

    Returns {"filename", "size_bytes", "storage_path"} — storage_path is
    None when upload=False. Raises BackupError on any failure: wrong
    database engine, missing pg_dump binary, or a non-zero pg_dump exit.
    """
    db = settings.DATABASES["default"]
    if db["ENGINE"] != "django.db.backends.postgresql":
        raise BackupError(
            "Automated backup only supports PostgreSQL (DB_ENGINE=postgresql); "
            f"got {db['ENGINE']!r}."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"casset_{timestamp}.dump"

    with tempfile.TemporaryDirectory() as tmp_dir:
        dest = Path(tmp_dir) / filename
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

        try:
            subprocess.run(  # noqa: S603 — args are settings-derived, not user input
                cmd, env=env, check=True, capture_output=True, text=True,
            )
        except FileNotFoundError as exc:
            raise BackupError(
                "pg_dump was not found on PATH. Install the PostgreSQL client tools."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise BackupError(f"pg_dump failed: {exc.stderr}") from exc

        size_bytes = dest.stat().st_size
        storage_path = None
        if upload:
            with open(dest, "rb") as fh:
                storage_path = default_storage.save(f"backups/{filename}", File(fh))

    return {"filename": filename, "size_bytes": size_bytes, "storage_path": storage_path}
