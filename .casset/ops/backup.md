# Casset — استراتژی بک‌آپ

## دستور

```powershell
python manage.py backup_db --output-dir /var/backups/casset
```

فقط روی `DB_ENGINE=postgresql` کار می‌کند (طبق Constitution، production همیشه Postgres است).
خروجی یک فایل `pg_dump --format=custom` با timestamp است — قابل restore با `pg_restore`.

## Cron پیشنهادی (روزانه، ساعت ۳ بامداد)

```cron
0 3 * * * cd /path/to/casset && DJANGO_SETTINGS_MODULE=config.settings.prod \
    /path/to/venv/bin/python manage.py backup_db --output-dir /var/backups/casset \
    >> /var/log/casset-backup.log 2>&1
```

## Restore

```bash
pg_restore --host=$DB_HOST --username=$DB_USER --dbname=casset --clean /var/backups/casset/casset_20260101_030000.dump
```

## نکات

- فایل‌های بک‌آپ را جدا از سرور دیتابیس نگه دارید (S3/Object Storage یا سرور دیگر) — بک‌آپ روی همان دیسک دیتابیس در صورت خرابی دیسک بی‌فایده است.
- سیاست نگه‌داری پیشنهادی: ۷ بک‌آپ روزانه + ۴ هفتگی + ۳ ماهانه (rotate با یک اسکریپت جدا یا ابزار provider مثل Arvan/Liara که معمولاً backup لایه‌ی زیرساخت هم دارند — این دستور مکمل آن است، نه جایگزین).
- قبل از هر migration بزرگ روی production، یک بک‌آپ دستی با همین دستور بگیرید.
