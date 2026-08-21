# S10 — بستن شکاف‌های امنیتی/عملیاتی — گزارش اجرا

**تاریخ:** ۲۰۲۶-۰۸-۲۱
**برنچ:** `claude/s10-security-ops-r0osad` (بر اساس `master` بعد از تگ `v2.0.0`)
**سند مرجع:** `.casset/releases/v2.1.0-phase2-plan.md` §۵ (S10)
**نتیجه‌ی نهایی:** هر ۵ تسک انجام و commit شدند. ۶۲۹ تست سبز (از ۵۹۲ baseline)،
`ruff check .` تمیز، پوشش تست ۹۲٪ (بدون افت).

---

## تسک ۱ — تأیید ایمیل برای ثبت‌نام با رمز

**تاریخ:** ۲۰۲۶-۰۸-۲۱
**فایل‌های تغییریافته:**
- `accounts/models.py` (مدل جدید `EmailVerification`)
- `accounts/migrations/0006_emailverification.py`
- `accounts/services.py` (`issue_email_verification`, `verify_email_token`,
  `find_unverified_user_by_email`, `seconds_until_email_resend`, `send_verification_email`)
- `accounts/forms.py` (`LoginForm.confirm_login_allowed`, `ResendVerificationForm`)
- `accounts/views.py` (`register_view`, `verify_email_view`, `resend_verification_email_view`,
  `CassetLoginView`)
- `accounts/urls.py`
- `templates/accounts/verify_email_sent.html`, `verify_email_result.html`, `verify_email_resend.html`,
  `verification_email.txt`, `verification_email_subject.txt`, `login.html` (به‌روزرسانی)
- `accounts/tests.py` (یک assertion موجود به‌روزرسانی شد)

**خلاصه‌ی تصمیم:** به‌جای فیلد بولی جدید، از `UserProfile.email_verified_at` موجود
(که برای ورود گوگل از قبل بود) استفاده شد. حساب‌های ثبت‌نام با رمز حالا
`is_active=False` ساخته می‌شوند — دقیقاً همان مکانیزمی که تعلیق حساب استفاده
می‌کند و در همه‌جا (پسورد/OTP/گوگل) از قبل چک می‌شود. تا وقتی لینک تایید
(hash شده sha256، انقضای ۲۴ساعته، یک‌بارمصرف) redeem نشود، لاگین امکان‌پذیر
نیست.

**باگ واقعی کشف و رفع‌شده حین توسعه:** چک اولیه‌ی گیت (`not profile.email_verified`)
تست موجود `test_suspended_user_blocked_with_persian_message` را می‌شکست — یک
حساب legacy که مستقیم `is_active=False` شده (نه از مسیر ثبت‌نام جدید، مثلاً
تعلیق دستی staff) پیام «ایمیل تایید نشده» می‌گرفت به‌جای پیام صحیح «حساب
تعلیق شده». رفع شد با شرط اضافه‌ی `user.email_verifications.exists()` — فقط
حسابی که واقعاً از ثبت‌نام جدید یک ردیف `EmailVerification` گرفته این پیام
جدید را می‌بیند؛ حساب‌های قدیمی/legacy رفتار قبلی را حفظ می‌کنند.

**تست‌های اضافه‌شده:** `accounts/tests_email_verification.py` — ۱۴ تست:
ثبت‌نام حساب را inactive می‌سازد و ایمیل می‌فرستد؛ حساب تایید-نشده نمی‌تواند
لاگین کند (با پیام و لینک resend)؛ توکن معتبر فعال‌سازی+لاگین می‌کند؛ توکن
غلط/منقضی/uid نامعتبر رد می‌شوند؛ کلیک دوباره روی لینک استفاده‌شده idempotent
است؛ resend برای حساب unverified ایمیل جدید می‌فرستد؛ resend برای ایمیل
ناموجود/حساب already-verified همان پیام عمومی را می‌دهد (بدون user-enumeration)؛
resend هم به cooldown و هم به IP rate limit محدود است.

**وضعیت:** Done.

---

## تسک ۲ — Rate limit روی فرم‌های لاگین و ثبت‌نام

**تاریخ:** ۲۰۲۶-۰۸-۲۱
**فایل‌های تغییریافته:**
- `accounts/views.py` (`CassetLoginView.post`, `_account_login_blocked`,
  `_bump_account_login_failure`, ثابت‌های `LOGIN_IP_LIMIT`/`LOGIN_ACCOUNT_LIMIT`،
  و rate limit موجود روی `register_view` که در تسک ۱ اضافه شده بود این‌جا ۴۲۹ گرفت)

**خلاصه‌ی تصمیم:** بدون وابستگی جدید (`django-ratelimit` در `pyproject.toml`
نبود و اضافه نشد) — همان الگوی cache-counter موجود پروژه (`_rate_limited`،
که از قبل روی OTP/جستجو بود) تعمیم یافت به لاگین. دو سقف مستقل: IP-wide
(۲۰ درخواست/۱۰دقیقه، جلوی username-spray از یک IP)، و per-account
(۵ تلاش ناموفق/۱۵دقیقه — فقط شکست شمارش می‌شود تا کاربر واقعی که چند بار
اشتباه تایپ کرده و بعد موفق می‌شود قفل نشود). هر دو **قبل از** رسیدن درخواست
به auth backend چک می‌شوند و پاسخ ۴۲۹ با پیام فارسی و صفحه‌ی معمولی لاگین
برمی‌گردانند (نه یک صفحه خطای خام جنگو).

**تست‌های اضافه‌شده:** `accounts/tests_rate_limit.py` — ۶ تست: سقف per-account
بعد از ۵ شکست بلاک می‌کند؛ حتی رمز درست هم بعد از بلاک رد می‌شود؛ لاگین موفق
شمارنده‌ی حساب را افزایش نمی‌دهد؛ سقف IP-wide حمله‌ی توزیع‌شده روی حساب‌های
مختلف را بلاک می‌کند؛ پاسخ بلاک‌شده پیام کاربرپسند دارد نه ۴۲۹ خام؛ سقف
ثبت‌نام هم بعد از ۱۰ درخواست بلاک می‌کند.

**وضعیت:** Done.

---

## تسک ۳ — بررسی fail-fast بودن SECRET_KEY / PLAY_IP_SALT / PLAY_UA_SALT

**تاریخ:** ۲۰۲۶-۰۸-۲۱
**فایل‌های تغییریافته:** `core/tests_settings_secrets.py` (جدید — هیچ فایل
تولیدی/config تغییر نکرد)

**خلاصه‌ی تصمیم:** بررسی مستقیم `config/settings/base.py::_require_secret`
نشان داد این تابع **از قبل** درست پیاده‌سازی شده بود: در نبود env و
`dev_fallback=False` (یعنی حالت production-like، `DEBUG=False`)
`ImproperlyConfigured` صریح پرتاب می‌کند؛ در dev یک مقدار تصادفی امن با
هشدار تولید می‌کند. این آیتم در سند فاز ۲ به‌عنوان «بررسی‌نشده» علامت‌گذاری
شده بود، نه «باگ شناخته‌شده» — پس هیچ کد تولیدی تغییر نکرد، فقط تست تاییدی
اضافه شد.

**تست‌های اضافه‌شده:** `core/tests_settings_secrets.py` — ۶ تست: سه تست واحد
مستقیم روی `_require_secret` (رد می‌کند بدون fallback، مقدار تولید می‌کند
با fallback، مقدار صریح را دست‌نخورده برمی‌گرداند)؛ سه تست subprocess-integration
که واقعاً `config.settings.prod` را در یک پردازش پایتون کاملاً جدا با یک env
دستی بالا می‌آورند: با هر سه secret حاضر بدون خطا بالا می‌آید؛ حذف تک‌تک هر
کدام از سه secret باعث خروج غیرصفر و `ImproperlyConfigured` می‌شود که نام
متغیر را ذکر می‌کند؛ مقدار خالی (نه فقط غایب) هم رد می‌شود.

**وضعیت:** Done (بدون تغییر کد — فقط تایید + تست رگرسیون).

---

## تسک ۴ — بک‌آپ خودکار زمان‌بندی‌شده

**تاریخ:** ۲۰۲۶-۰۸-۲۱
**فایل‌های تغییریافته:**
- `core/backup.py` (جدید — `run_database_backup`, `BackupError`)
- `core/tasks.py` (جدید — `backup_database_task`، Celery shared_task)
- `config/settings/base.py` (`CELERY_BEAT_SCHEDULE["daily-database-backup"]`،
  `BACKUP_SCHEDULE_HOUR`/`MINUTE`)
- `.env.example`, `.casset/ops/backup.md` (مستندسازی مسیر جدید)

**خلاصه‌ی تصمیم:** دستور دستی موجود `core/management/commands/backup_db.py`
(pg_dump به دیسک محلی، تست‌های موجودش) عمداً **دست‌نخورده** ماند تا ریسک
regression صفر باشد. یک مسیر جدید و مستقل اضافه شد: `run_database_backup`
همان منطق pg_dump را در یک `TemporaryDirectory` اجرا می‌کند، سپس نتیجه را
با `django.core.files.storage.default_storage` (همان S3-compatible backend
که فایل‌های مدیا در prod با `USE_S3_STORAGE=1` استفاده می‌کنند) زیر
`backups/` آپلود می‌کند و فایل موقت را حذف می‌کند. Celery beat این را روزانه
ساعت ۰۳:۰۰ (پیش‌فرض، با env قابل‌تنظیم) صدا می‌زند. شکست (موتور غیر-Postgres،
pg_dump غایب، خطای pg_dump) یک `BackupError` پرتاب می‌کند که catch نمی‌شود —
Celery این اجرا را FAILED ثبت می‌کند (قابل‌دیدن در مانیتورینگ/Sentry)، نه
یک no-op خاموش.

**تست‌های اضافه‌شده:** `core/tests_backup.py` — ۱۱ تست: رد روی SQLite؛ آپلود
موفق به storage با پیشوند `backups/`؛ `upload=False` هیچ storage.save صدا
نمی‌زند؛ pg_dump غایب و خطای pg_dump هر دو `BackupError` می‌دهند (با stderr
واقعی در پیام)؛ دایرکتوری موقت بعد از اجرا واقعاً پاک می‌شود؛ تسک Celery
موفقیت را برمی‌گرداند و روی خطا re-raise می‌کند (نه catch خاموش)؛ نام تسک و
حضور در `CELERY_BEAT_SCHEDULE` تایید می‌شود؛ یک تست بدون هیچ mock روی
دیتابیس واقعی SQLite این test suite (نه mock) رد صحیح "wrong engine" را تایید
می‌کند.

**وضعیت:** Done.

---

## تسک ۵ — CI واقعی + `.gitattributes`

**تاریخ:** ۲۰۲۶-۰۸-۲۱
**فایل‌های تغییریافته:**
- `.github/workflows/ci.yml` (جدید)
- `.gitattributes` (جدید)
- `scripts/generate_avatars.py`, `accounts/management/commands/generate_avatars.py`
  (رفع مکانیکی ۸ خطای ruff از قبل موجود — ترتیب import + یک import بلااستفاده،
  بدون تغییر رفتار)

**خلاصه‌ی تصمیم:** `.github/workflows/ci.yml` روی هر PR و هر push به
`master` اجرا می‌شود: نصب وابستگی‌ها (`pip install -e ".[dev]"`) روی Python
3.12 (کف بازه‌ی `requires-python` در `pyproject.toml`)، `ruff check .`،
`makemigrations --check --dry-run` (جلوگیری از drift مدل/migration)،
`manage.py check`، و کل test suite زیر `coverage` با آپلود گزارش به‌عنوان
artifact. `.gitattributes` با `* text=auto eol=lf` (+ مارک `binary` صریح
روی مدیا/فونت) دقیقاً همان راه‌حلی است که ممیزی ۲۰۲۶-۰۸-۲۱ برای مشکل
«۲۳۵ فایل CRLF کاذب» پیشنهاد داده بود.

فعال‌کردن gate `ruff check .` نیاز داشت ۸ خطای از قبل موجود (نامرتبط با
S10) در دو نسخه‌ی اسکریپت avatar generation رفع شود — صرفاً ترتیب import و
یک import بلااستفاده (`ImageFont`)، بدون تغییر رفتار (تایید شد: کل test
suite بعد از این رفع هم ۶۲۹/۶۲۹ سبز ماند).

**تست‌های اضافه‌شده:** ندارد (این تسک زیرساخت CI است، نه کد تولیدی؛ خود
اجرای موفق `ruff check .` + کل test suite زیر `coverage` روی محیط محلی، قبل
از commit، شاهد صحت workflow است).

**وضعیت:** Done.

---

## خلاصه‌ی نهایی

| معیار | قبل از S10 | بعد از S10 |
|---|---|---|
| تعداد تست (SQLite) | ۵۹۲ (۱ skip) | **۶۲۹ (۱ skip)** |
| پوشش تست | ۹۲٪ | **۹۲٪** (بدون افت) |
| `ruff check .` | ۸ خطای pre-existing | **تمیز** |
| CI واقعی | نبود | `.github/workflows/ci.yml` |
| بک‌آپ خودکار | فقط دستی/دیسک محلی | Celery beat روزانه + Object Storage |

**تایید نشده در این نشست:** اجرای کامل test suite روی PostgreSQL واقعی
(`scripts/local_postgres.py test`) — سرور pgserver در این محیط sandbox
از طریق Unix socket درست بالا آمد و پاسخ داد، ولی `127.0.0.1:5432` (که
Django برای اتصال به آن نیاز دارد) توسط شبکه‌ی sandbox مسدود بود
(`Connection refused`). این یک محدودیت محیطی مستند است، نه یک باگ کد —
مشابه دقیقاً همان مشکل tzdata که قبلاً برای همین ابزار در همین سند ثبت شده
بود. هیچ‌کدام از کد جدید این Sprint از SQL خام یا aggregate خاص دیتابیس
استفاده نمی‌کند (کلاس باگی که این تایید قبلاً لو داده بود)، پس ریسک واقعی کم
است. **توصیه:** قبل از merge نهایی روی `master`، یک بار دیگر
`python scripts/local_postgres.py test` روی محیطی با دسترسی TCP کامل (مثلاً
ماشین PYMN) اجرا شود.
