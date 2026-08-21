# Casset — صف کار خودکار (Autonomous Task Queue)

> این فایل توسط Scheduled Task «casset-autonomous-cycle» خوانده می‌شود.
> هر اجرا **دقیقاً یک آیتم** با وضعیت `⬜ pending` را برمی‌دارد، روی یک branch جدا کار می‌کند،
> و وضعیتش را به `🔄 in-review` تغییر می‌دهد. هرگز به `main` push/merge نمی‌کند.
>
> **قانون کاربر (PYMN):** آیتم جدید فقط با اضافه‌کردن یک خط زیر همین بخش. حذف نکن، فقط وضعیت را عوض کن.
> علائم وضعیت: `⬜ pending` (منتظر اجرا) · `🔄 in-review` (انجام شد، منتظر بازبینی تو) · `✅ done` (تو تایید کردی) · `❌ rejected` (رد شد، دلیل را در گزارش بنویس)

---

## صف

_(همه‌ی آیتم‌های قبلی در ممیزی ۲۰۲۶-۰۸-۲۱ بررسی و به آرشیو منتقل شدند — جزئیات کامل در `.casset/state/audit-2026-08-21.md`)_

_(صف فعلاً خالی است — هر ۴ آیتم S11 در همین Sprint بسته شدند، به آرشیو زیر نگاه کن.)_

---

## آرشیو (تکمیل‌شده)

- ✅ done (2026-08-22, S11) | مدل رسمی `PlaybackSession` — session جدید به‌ازای هر تلاش پخش (نه فقط هر روز)؛ `register_play`/`register_progress` بدون تغییر شکل API وصل شدند؛ data migration از `PlayEvent` موجود. ۶ تست.
- ✅ done (2026-08-22, S11) | سیگنال ضدتقلب روی play events — Gate ۰ جدید: نرخ IP غیرعادی (نرم/سخت) + پخش کوتاه تکراری از یک کاربر؛ بلاک فقط `PointLedger`/`PlaybackSession`، هیچ‌وقت مسدودسازی حساب. ۶ تست.
- ✅ done (2026-08-22, S11) | Immutable بودن `AuditLog` در سطح ORM — `save`/`delete` رد می‌شوند روی رکورد موجود؛ `QuerySet.update()/.delete()/.bulk_update()` هم مسدود. ۶ تست.
- ✅ done (2026-08-22, S11) | اتصال `DailyTrackStat` به داشبورد — باگ واقعی `points_awarded` رفع شد؛ Celery beat روزانه؛ endpoint `GET /api/v1/creator/stats/`؛ دکمه‌های روزانه/هفتگی/ماهانه در `creator_studio.html`. ۱۵ تست، تایید دستی end-to-end در مرورگر.

- ✅ done (2026-08-21, S10) | تأیید ایمیل برای ثبت‌نام با رمز — `accounts.models.EmailVerification` + `issue_email_verification`/`verify_email_token` در `services.py`، گیت روی `is_active` (همان مکانیزم تعلیق حساب). ۱۴ تست.
- ✅ done (2026-08-21, S10) | Rate limit لاگین/ثبت‌نام — IP-wide (۲۰/۱۰د) + per-account روی شکست (۵/۱۵د) در `CassetLoginView.post`؛ ۶ تست.
- ✅ done (2026-08-21, S10) | بررسی `SECRET_KEY`/`PLAY_IP_SALT`/`PLAY_UA_SALT` — **نتیجه: از قبل درست fail-fast بود** (`_require_secret` در `base.py`)، فقط تست تاییدی (واحد + subprocess-integration واقعی روی `config.settings.prod`) اضافه شد، کد تغییر نکرد. ۶ تست.
- ✅ done (2026-08-21, S10) | بک‌آپ خودکار زمان‌بندی‌شده — `core/backup.py` + Celery beat (`core.backup_database`، روزانه ۰۳:۰۰ قابل‌تنظیم) آپلود به Object Storage پیکربندی‌شده (`default_storage`)؛ دستور دستی `backup_db` دست‌نخورده ماند. ۱۱ تست.
- ✅ done (2026-08-21, S10) | CI واقعی + `.gitattributes` — `.github/workflows/ci.yml` (ruff + migrations check + full test + coverage)، `.gitattributes` با `* text=auto eol=lf`. ۸ خطای ruff از قبل موجود در اسکریپت‌های avatar هم مکانیکی رفع شد تا gate سبز باشد.

- ✅ done (2026-08-21) | حذف `config/settings.py` — تایید نهایی: فایل در فایل‌سیستم وجود ندارد، هیچ import برهنه‌ای در کد پیدا نشد. بسته.
- ✅ done (2026-08-21) | پاکسازی ریشه مخزن — **یافته ممیزی:** از قبل کامل انجام شده. `.gitignore` همین حالا `db.sqlite3.backup*`، `*.zip`، `__pycache__/`، `*.egg-info/` را پوشش می‌دهد و `git ls-files` تأیید کرد هیچ‌کدام tracked نیستند. فایل‌های `folders.txt`/`project_structure.txt` روی دیسک اصلاً وجود ندارند (قبلاً حذف شده‌اند). کاری لازم نبود.
- ✅ done (2026-08-21) | مقایسه `pyproject.toml`/`requirements_current.txt` — **یافته:** فایل `requirements_current.txt` (و هر `requirements*.txt`) در ریشه مخزن وجود ندارد؛ `pyproject.toml` تنها منبع وابستگی‌هاست. موضوع منتفی است.
- ✅ done (2026-08-21) | اندازه‌گیری پوشش تست — انجام شد روی سیستم واقعی PYMN: **۹۲٪** (۵۹۱ تست، `OK skipped=1`)، جایگزین عدد قدیمی ۸۱٪ در `current.md`.
