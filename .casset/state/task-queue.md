# Casset — صف کار خودکار (Autonomous Task Queue)

> این فایل توسط Scheduled Task «casset-autonomous-cycle» خوانده می‌شود.
> هر اجرا **دقیقاً یک آیتم** با وضعیت `⬜ pending` را برمی‌دارد، روی یک branch جدا کار می‌کند،
> و وضعیتش را به `🔄 in-review` تغییر می‌دهد. هرگز به `main` push/merge نمی‌کند.
>
> **قانون کاربر (PYMN):** آیتم جدید فقط با اضافه‌کردن یک خط زیر همین بخش. حذف نکن، فقط وضعیت را عوض کن.
> علائم وضعیت: `⬜ pending` (منتظر اجرا) · `🔄 in-review` (انجام شد، منتظر بازبینی تو) · `✅ done` (تو تایید کردی) · `❌ rejected` (رد شد، دلیل را در گزارش بنویس)

---

## صف

- ⬜ pending | فایل `config/settings.py` را با پکیج `config/settings/` مقایسه کن؛ اگر واقعاً مرده و بدون import فعال است، حذفش کن؛ `manage.py check` و کل تست‌سوییت را اجرا کن تا مطمئن شوی هیچ‌جا به آن ارجاع نمی‌دهد.
- ⬜ pending | ریشه مخزن را پاکسازی کن: `db.sqlite3.backup*`, `db12agu2026.zip`, `folders.txt`, `project_structure.txt`, `__pycache__/`, `casset.egg-info/` را در `.gitignore` اضافه کن (فایل‌های موجود را حذف نکن مگر مطمئنی نیاز نیستند — فقط گزارش بده کدام‌ها safe-to-delete هستند).
- ⬜ pending | `pyproject.toml` و `requirements_current.txt` را مقایسه کن؛ گزارش بده کدام یکی منسوخ است و چرا؛ کاری تغییر نده، فقط پیشنهاد بده.
- ⬜ pending | پوشش تست فعلی را با `pytest --cov` اندازه بگیر (در صورت نبود pytest-cov، نصبش کن در محیط sandbox) و عدد baseline را در `.casset/state/current.md` ثبت کن.
- ⬜ pending | `config/settings/base.py` را بررسی کن: آیا `SECRET_KEY`, `PLAY_IP_SALT`, `PLAY_UA_SALT` در نبود env واقعاً fail می‌کنند یا fallback بی‌صدا دارند؟ فقط گزارش بده، تغییر نده مگر آیتم بعدی صریحاً اجازه بدهد.

---

## آرشیو (تکمیل‌شده)

_(هنوز خالی — بعد از هر تایید کاربر، آیتم به اینجا منتقل می‌شود)_
