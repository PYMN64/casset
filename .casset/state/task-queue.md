# Casset — صف کار خودکار (Autonomous Task Queue)

> این فایل توسط Scheduled Task «casset-autonomous-cycle» خوانده می‌شود.
> هر اجرا **دقیقاً یک آیتم** با وضعیت `⬜ pending` را برمی‌دارد، روی یک branch جدا کار می‌کند،
> و وضعیتش را به `🔄 in-review` تغییر می‌دهد. هرگز به `main` push/merge نمی‌کند.
>
> **قانون کاربر (PYMN):** آیتم جدید فقط با اضافه‌کردن یک خط زیر همین بخش. حذف نکن، فقط وضعیت را عوض کن.
> علائم وضعیت: `⬜ pending` (منتظر اجرا) · `🔄 in-review` (انجام شد، منتظر بازبینی تو) · `✅ done` (تو تایید کردی) · `❌ rejected` (رد شد، دلیل را در گزارش بنویس)

---

## صف

- 🔄 in-review | فایل `config/settings.py` را با پکیج `config/settings/` مقایسه کن؛ اگر واقعاً مرده و بدون import فعال است، حذفش کن؛ `manage.py check` و کل تست‌سوییت را اجرا کن تا مطمئن شوی هیچ‌جا به آن ارجاع نمی‌دهد. — **یافته:** این حذف از قبل در commit `ea1d08b` ("chore: delete dead settings.py and stray repo-root dump files") روی همین branch (`stabilization/v1-baseline`) انجام و کامیت شده بود؛ صف هنوز `⬜ pending` مانده بود چون بعد از آن commit به‌روزرسانی نشده بود. این اجرا (branch `auto/2026-08-20-verify-settings-cleanup`) فقط دوباره تایید کرد: `config/settings.py` در فایل‌سیستم وجود ندارد، و هیچ `import config.settings` برهنه (بدون `.dev`/`.prod`) در هیچ‌کدام از اپ‌ها/`manage.py`/`wsgi.py`/`asgi.py` پیدا نشد. **نتوانستم** `manage.py check`/تست‌سوییت واقعی را در این sandbox اجرا کنم — جزئیات در گزارش. نیاز به تایید نهایی PYMN که این وضعیت را ✅ کند.
- ⬜ pending | ریشه مخزن را پاکسازی کن: `db.sqlite3.backup*`, `db12agu2026.zip`, `folders.txt`, `project_structure.txt`, `__pycache__/`, `casset.egg-info/` را در `.gitignore` اضافه کن (فایل‌های موجود را حذف نکن مگر مطمئنی نیاز نیستند — فقط گزارش بده کدام‌ها safe-to-delete هستند).
- ⬜ pending | `pyproject.toml` و `requirements_current.txt` را مقایسه کن؛ گزارش بده کدام یکی منسوخ است و چرا؛ کاری تغییر نده، فقط پیشنهاد بده.
- ⬜ pending | پوشش تست فعلی را با `pytest --cov` اندازه بگیر (در صورت نبود pytest-cov، نصبش کن در محیط sandbox) و عدد baseline را در `.casset/state/current.md` ثبت کن.
- ⬜ pending | `config/settings/base.py` را بررسی کن: آیا `SECRET_KEY`, `PLAY_IP_SALT`, `PLAY_UA_SALT` در نبود env واقعاً fail می‌کنند یا fallback بی‌صدا دارند؟ فقط گزارش بده، تغییر نده مگر آیتم بعدی صریحاً اجازه بدهد.

---

## آرشیو (تکمیل‌شده)

_(هنوز خالی — بعد از هر تایید کاربر، آیتم به اینجا منتقل می‌شود)_
