# Casset — استراتژی بک‌آپ

## ۱. بک‌آپ خودکار زمان‌بندی‌شده (S10 — روش پیش‌فرض از این به بعد)

`core/tasks.py::backup_database_task` (Celery beat، `config/settings/base.py::
CELERY_BEAT_SCHEDULE["daily-database-backup"]`) هر روز به‌صورت خودکار اجرا
می‌شود: همان منطق `pg_dump --format=custom` را در یک دایرکتوری موقت اجرا
می‌کند و سپس فایل را در Object Storage پیکربندی‌شده‌ی پروژه (`core/backup.py::
run_database_backup` → `django.core.files.storage.default_storage` — یعنی
همان S3-compatible backend که `USE_S3_STORAGE=1` را در prod فعال می‌کند، زیر
پیشوند `backups/`) آپلود می‌کند، نه دیسک لوکال ورکر.

نیازمندی‌ها:
- یک `celery -A config beat` واقعی در حال اجرا در production (بدون آن، ورودی
  `CELERY_BEAT_SCHEDULE` هیچ‌وقت شلیک نمی‌شود — این خودش را در dev/test اجرا
  نمی‌کند چون `CELERY_TASK_ALWAYS_EAGER` است).
- زمان‌بندی با `BACKUP_SCHEDULE_HOUR`/`BACKUP_SCHEDULE_MINUTE` (پیش‌فرض ۰۳:۰۰)
  در `.env` قابل تنظیم است.
- شکست (pg_dump غایب، خطای pg_dump، یا موتور غیر-Postgres) به‌صورت
  `core.backup.BackupError` پرتاب می‌شود — Celery این تسک را FAILED ثبت
  می‌کند (قابل‌دیدن در Sentry/مانیتورینگ در صورت پیکربندی)، نه یک no-op خاموش.

اجرای دستی همین مسیر (بدون منتظرماندن برای schedule):
```python
from core.tasks import backup_database_task
backup_database_task.delay()  # یا فراخوانی مستقیم برای اجرای هم‌زمان
```

## ۲. دستور دستی محلی (بدون آپلود — برای یک بک‌آپ سریع روی دیسک عملیات)

```powershell
python manage.py backup_db --output-dir /var/backups/casset
```

فقط روی `DB_ENGINE=postgresql` کار می‌کند (طبق Constitution، production همیشه Postgres است).
خروجی یک فایل `pg_dump --format=custom` با timestamp است — قابل restore با `pg_restore`.
این دستور **فقط دیسک محلی** می‌نویسد (تغییری نکرده) — برای بک‌آپ خودکار
همیشه‌در-Object-Storage از بخش ۱ بالا (Celery beat) استفاده کن.

### Cron جایگزین (اختیاری، اگر Celery beat در دسترس نیست)

```cron
0 3 * * * cd /path/to/casset && DJANGO_SETTINGS_MODULE=config.settings.prod \
    /path/to/venv/bin/python manage.py backup_db --output-dir /var/backups/casset \
    >> /var/log/casset-backup.log 2>&1
```

## Restore

```bash
pg_restore --host=$DB_HOST --username=$DB_USER --dbname=casset --clean /var/backups/casset/casset_20260101_030000.dump
```

(بک‌آپ‌های آپلودشده در بخش ۱ را اول با storage provider (S3/Arvan/Liara/MinIO)
دانلود کن، سپس همین `pg_restore` را روی فایل دانلودشده اجرا کن.)

## نکات

- سیاست نگه‌داری پیشنهادی: ۷ بک‌آپ روزانه + ۴ هفتگی + ۳ ماهانه (rotate با یک اسکریپت جدا یا ابزار provider مثل Arvan/Liara که معمولاً backup لایه‌ی زیرساخت هم دارند — این دستور مکمل آن است، نه جایگزین). این پروژه خودش rotate/expiry فایل‌های قدیمی را پیاده نمی‌کند — سیاست lifecycle را روی خود باکت تنظیم کن.
- قبل از هر migration بزرگ روی production، یک بک‌آپ دستی با دستور بخش ۲ بگیرید.
