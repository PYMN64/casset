"""core/tests_backup.py — S10 item 4: scheduled backup wired to Celery beat
and uploaded to the project's configured object storage.

Kept separate from core/tests.py::BackupDbCommandTests, which covers the
existing local-disk-only `manage.py backup_db` management command (unchanged
here — still documented in .casset/ops/backup.md for a manual/cron run).
core/backup.py is the new, additive path the scheduled Celery task
(core/tasks.py::backup_database_task) actually calls.
"""

from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from core.backup import BackupError, run_database_backup
from core.tasks import backup_database_task


def _fake_pg_dump(cmd, **kwargs):
    file_arg = next(a for a in cmd if a.startswith("--file="))
    with open(file_arg.split("=", 1)[1], "wb") as f:
        f.write(b"x" * 256)


POSTGRES_SETTINGS = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "casset", "USER": "casset_user", "PASSWORD": "secret",
        "HOST": "dbhost", "PORT": "5432",
    }
}


class RunDatabaseBackupTests(TestCase):
    @patch("core.backup.settings")
    def test_refuses_on_sqlite(self, mock_settings):
        mock_settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}
        with self.assertRaises(BackupError):
            run_database_backup()

    @patch("core.backup.default_storage")
    @patch("core.backup.subprocess.run", side_effect=_fake_pg_dump)
    @patch("core.backup.settings")
    def test_uploads_dump_to_configured_storage(self, mock_settings, mock_run, mock_storage):
        mock_settings.DATABASES = POSTGRES_SETTINGS
        mock_storage.save.return_value = "backups/casset_20260101_030000.dump"

        result = run_database_backup(upload=True)

        self.assertEqual(mock_storage.save.call_count, 1)
        saved_path = mock_storage.save.call_args.args[0]
        self.assertTrue(saved_path.startswith("backups/"))
        self.assertEqual(result["storage_path"], "backups/casset_20260101_030000.dump")
        self.assertEqual(result["size_bytes"], 256)
        self.assertTrue(result["filename"].startswith("casset_"))

    @patch("core.backup.default_storage")
    @patch("core.backup.subprocess.run", side_effect=_fake_pg_dump)
    @patch("core.backup.settings")
    def test_upload_false_skips_storage_entirely(self, mock_settings, mock_run, mock_storage):
        mock_settings.DATABASES = POSTGRES_SETTINGS

        result = run_database_backup(upload=False)

        mock_storage.save.assert_not_called()
        self.assertIsNone(result["storage_path"])

    @patch("core.backup.subprocess.run", side_effect=FileNotFoundError())
    @patch("core.backup.settings")
    def test_missing_pg_dump_binary_raises_backup_error(self, mock_settings, mock_run):
        mock_settings.DATABASES = POSTGRES_SETTINGS
        with self.assertRaises(BackupError):
            run_database_backup()

    @patch("core.backup.settings")
    def test_pg_dump_process_failure_raises_backup_error_with_stderr(self, mock_settings):
        import subprocess as real_subprocess

        mock_settings.DATABASES = POSTGRES_SETTINGS
        with patch(
            "core.backup.subprocess.run",
            side_effect=real_subprocess.CalledProcessError(1, ["pg_dump"], stderr="disk full"),
        ), self.assertRaises(BackupError) as ctx:
            run_database_backup()
        self.assertIn("disk full", str(ctx.exception))

    def test_real_tempdir_is_cleaned_up_after_run(self):
        """The dump file is written under a TemporaryDirectory that must
        not survive the call — nothing should leak onto local disk once
        upload=True has moved the bytes into storage."""
        captured = {}

        def _capture_and_dump(cmd, **kwargs):
            file_arg = next(a for a in cmd if a.startswith("--file="))
            path = Path(file_arg.split("=", 1)[1])
            captured["dir"] = path.parent
            path.write_bytes(b"x" * 10)

        with patch("core.backup.settings") as mock_settings, \
             patch("core.backup.subprocess.run", side_effect=_capture_and_dump), \
             patch("core.backup.default_storage") as mock_storage:
            mock_settings.DATABASES = POSTGRES_SETTINGS
            mock_storage.save.return_value = "backups/whatever.dump"
            run_database_backup(upload=True)

        self.assertFalse(captured["dir"].exists())


class BackupDatabaseTaskTests(TestCase):
    @patch("core.tasks.run_database_backup")
    def test_task_returns_result_on_success(self, mock_run):
        mock_run.return_value = {
            "filename": "casset_x.dump", "size_bytes": 123, "storage_path": "backups/casset_x.dump",
        }
        result = backup_database_task()
        self.assertEqual(result["filename"], "casset_x.dump")
        mock_run.assert_called_once_with(upload=True)

    @patch("core.tasks.run_database_backup", side_effect=BackupError("boom"))
    def test_task_reraises_on_failure_instead_of_swallowing(self, mock_run):
        """A scheduled backup that fails must surface as a real Celery
        task failure — never a silent no-op nobody notices."""
        with self.assertRaises(BackupError):
            backup_database_task()

    def test_task_is_registered_with_celery_name(self):
        self.assertEqual(backup_database_task.name, "core.backup_database")

    def test_beat_schedule_includes_daily_backup(self):
        from django.conf import settings

        self.assertIn("daily-database-backup", settings.CELERY_BEAT_SCHEDULE)
        entry = settings.CELERY_BEAT_SCHEDULE["daily-database-backup"]
        self.assertEqual(entry["task"], "core.backup_database")

    def test_real_run_against_test_sqlite_db_fails_fast_with_no_mocks(self):
        """No mocking at all: this test suite runs on SQLite
        (config.settings.dev default), so the real, unmocked
        run_database_backup must refuse with a traceable BackupError
        rather than attempting pg_dump against a database that isn't
        PostgreSQL."""
        with self.assertRaises(BackupError):
            run_database_backup(upload=False)
