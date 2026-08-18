# Casset — Architectural Change Log

> **راهنمای خواندن این فایل برای Claude:**
> این فایل را **اول از همه** در هر session بخوان — قبل از هر کد نوشتن یا تصمیم معماری.
> هر entry یک تغییر واقعی روی disk است، نه plan. اگه چیزی اینجا نیست، انجام نشده.
>
> فرمت هر entry:
> ```
> ## [YYYY-MM-DD] عنوان کوتاه
> **نوع:** Architecture | Bugfix | Refactor | Config | Docs
> **فایل‌های تغییرکرده:** ...
> **تصمیم:** چرا این کار انجام شد
> **اثر:** چه چیزی عوض شد
> **وضعیت CLAUDE.md:** کدام مورد بسته شد
> ```
>
> **قانون:** هر Claude که تغییری روی پروژه می‌ده، باید یک entry جدید بالای خط
> `## [2026-08-17] اسکن کامل پروژه — باگ‌های کریتیکال، Security، تست و نقص‌ها

## [2026-08-18] تست‌های کامل uploads/billing/moderation + ۴ باگ واقعی کشف و رفع شد

**نوع:** Bugfix + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `uploads/tests.py` — از استاب خالی به ۳۲ تست (فرم، quota روزانه/دقیقه‌ای، مالکیت، اعتبارسنجی فایل)
- `billing/tests.py` — ۱۳ تست جدید برای `create_payout_request`/`payout_page`/`vip_page` (قبلاً کاملاً بدون تست)
- `moderation/tests.py` — ۱۸ تست جدید برای `approve_track`/`reject_track`/`report_profile`/`track_queue`/`report_queue`
- `core/validators.py` — `validate_audio` فیکس شد (مقایسه غلط طول بایت که هر MP3 با تگ ID3v2 واقعی را رد می‌کرد)؛ `validate_image` از `imghdr` (deprecated، در پایتون ۳.۱۳ حذف می‌شود ولی pyproject تا ۳.۱۴ را پشتیبانی می‌کند) به Pillow منتقل شد؛ `validate_video` جدید اضافه شد
- `uploads/forms.py` — `TrackUploadForm` به `core.validators` وصل شد (`clean_cover`/`clean_audio`/`clean_video`)؛ باگ `tags_text` فیکس شد (پایین را ببین)
- `uploads/views.py` — سقف آپلود روزانه (`PlatformSetting.creator_daily_upload_limit`) که تعریف شده بود ولی هیچ‌جا enforce نمی‌شد، الان واقعاً اعمال می‌شود (VIP هم مشمول است، فقط سقف دقیقه رایگان را دور می‌زند)
- `billing/views.py` — `create_payout_request` قبل از ساخت درخواست جدید، وجود یک درخواست PENDING را چک می‌کند
- `moderation/views.py` — `approve_track`/`reject_track` idempotent شدند

**۴ باگ واقعی کشف‌شده حین نوشتن تست (نه فرضی — هرکدام با چرخه red→green ثابت شد):**

1. **`validate_audio` هر MP3 واقعی را رد می‌کرد** — `head = file.read(4)` (۴ بایت) با `b"ID3"` (۳ بایت) مقایسه می‌شد که هرگز برابر نیست؛ این تابع تا امروز dead code بود (هیچ‌جا import نمی‌شد) پس این باگ هیچ‌وقت لمس نشده بود.
2. **`tags_text` در آپلود/ویرایش ترک کاملاً بی‌اثر بود** — منطق ساخت Tag فقط داخل شاخه‌ی `commit=True` متد `save()` بود، ولی `upload_track`/`edit_track` همیشه با `commit=False` + `form.save_m2m()` صدا می‌زنن (الگوی استاندارد Django) — یعنی اون شاخه هرگز اجرا نمی‌شد. رفع شد با wrap کردن `save_m2m` (الگوی مستند Django برای پردازش سفارشی روی commit=False).
3. **درخواست تسویه تکراری** — هیچ‌چیز جلوی ثبت چند `PayoutRequest` هم‌زمان (هرکدام تا سقف کامل امتیاز کاربر) را نمی‌گرفت.
4. **نوتیفیکیشن تکراری در moderation** — کلیک دوباره روی approve/reject روی ترکی که از قبل همون وضعیت را داشت، هر بار نوتیفیکیشن جدید می‌ساخت و `published_at` را جابه‌جا می‌کرد (هیچ idempotency guard نبود).

**یافته‌ی جانبی — حل شد:** `CREATOR_DAILY_UPLOAD_LIMIT` (env-var در `config/settings/base.py` + `.env.example`) با `PlatformSetting.creator_daily_upload_limit` (admin-editable) همپوشانی داشت و در هیچ‌کجا استفاده نمی‌شد. با تأیید کاربر حذف شد — تنها منبع حقیقت سقف آپلود روزانه الان `PlatformSetting` است.

**اثر:** ۷۴ تست جدید اضافه شد (uploads ۳۲ + billing ۱۳ + moderation ۱۸ + بقیه). کل تست‌سوییت پروژه از ۱۶۴ به **۲۳۵ تست** رسید، همه pass. هر ۴ باگ با چرخه‌ی revert→fail→restore→pass تأیید شد، نه فقط ادعا.

**وضعیت CLAUDE.md:** جدول بخش ۳ نیازی به تغییر ندارد (این باگ‌ها جزو ۸ مورد اصلی نبودند). یافته‌ی امنیتی «آپلود بدون اعتبارسنجی» از گزارش قبلی همین session بسته شد.

---

## [2026-08-18] فیکس کریتیکال — کرش کامل فلوی ورود با شماره تلفن

**نوع:** Bugfix + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `accounts/views.py` — اضافه شدن `from django.conf import settings` (import گم‌شده)
- `accounts/tests.py` — ۱۶ تست جدید برای `phone_start_view`/`phone_verify_view` (کل فلوی OTP: ارسال کد، cooldown، نرمال‌سازی شماره، کد اشتباه/منقضی/بیش‌ازحد تلاش، ورود کاربر جدید در برابر کاربر موجود)

**تصمیم:** بازبینی کامل پروژه (تست کامل + امنیت + منطق کسب‌وکار، هر سه به‌صورت موازی) نشون داد `phone_start_view` از `settings.DEBUG` استفاده می‌کرد بدون اینکه `django.conf.settings` هیچ‌جای فایل import شده باشه — یعنی هر submit موفق فرم `/phone/` با `NameError` کرش می‌کرد. علتِ پنهون موندنش: صفر تست روی این view (نه در `accounts/tests.py` نه در smoke test)، و smoke test فقط GET می‌زد در حالی که کرش فقط در مسیر POST رخ می‌داد.

**اثر:** فلوی ورود با شماره تلفن (تنها مسیر ورود بدون رمز عبور پروژه) دوباره کار می‌کنه. رگرسیون با حذف موقت import و مشاهده‌ی مجدد همون NameError، سپس برگردوندن fix، صریحاً تأیید شد — یعنی تست‌های جدید واقعاً این کلاس باگ رو می‌گیرن. کل تست‌سوییت پروژه (۱۶۴ تست، قبلاً ۱۴۸ تا) بعد از فیکس pass می‌شه.

**وضعیت CLAUDE.md:** این باگ جزو ۸ مورد شناخته‌شده‌ی بخش ۳ نبود — در همین بازبینی کشف شد. جدول بخش ۳ نیاز به تغییر نداره.

**یافته‌های دیگر این بازبینی (هنوز باز، برای session‌های بعدی):**
- 🟠 آپلود فایل صوتی/ویدیویی بدون اعتبارسنجی نوع/سایز واقعی (`uploads/forms.py`, `tracks/models.py`)
- 🟡 ثبت پخش وضعیت انتشار ترک (status/visibility) رو چک نمی‌کنه (`plays/views.py`)
- 🟡 تایید OTP فاقد rate-limit سطح IP
- 🔵 `uploads/tests.py`, `billing/tests.py` (payout)، `moderation/tests.py` (approve/reject) عملاً بدون تست
- 🔵 سیگنال دوبل ساخت پروفایل (`accounts/models.py` + `accounts/signals.py`) — بی‌خطر ولی یک کوئری اضافه هر بار
- 🔵 فایل مرده `config/settings.py` با SECRET_KEY ناامن hardcoded (بی‌خطر، import نمی‌شه، ولی حذفش بهتره)

---

**نوع:** Bugfix + Security + Tests  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `accounts/models.py` — signal فعال شد (auto-create UserProfile)
- `accounts/views.py` — redirect loop حذف، OTP فقط در DEBUG نشان داده می‌شه، dashboard از PointLedger می‌خونه
- `accounts/tests.py` — 198 خط تست جدید (signal، register، login، onboarding، creator، middleware)
- `uploads/views.py` — منطق if/else نادرست quota فیکس شد
- `core/middleware.py` — MiddlewareMixin دپرکیت حذف، __init__/__call__ درست
- `CLAUDE.md` — مورد #۶ بسته شد

**باگ‌های حل‌شده:**
1. **CRITICAL** — UserProfile signal کامنت شده بود ، هر جایی user.profile دسترسی می‌شد احتمال AttributeError داشت
2. **CRITICAL** — redirect loop دوگانه در `public_profile` حذف شد
3. **SECURITY** — کد OTP در production به همه نشان داده می‌شد — حالا فقط DEBUG=True
4. **LOGIC** — dashboard از PlayEvent می‌خوند، نه PointLedger (منبع حقیقت)
5. **LOGIC** — uploads: VIP کاربر هیچوقت save نمی‌شد (دو شاخه if/else نادرست)
6. **DEPRECATED** — MiddlewareMixin برای Django 4+ دپرکیته

**وضعیت CLAUDE.md:** مورد #۶ بسته شد ✅

**موارد باز بعد از این session:**
- مورد #۴ (Postgres migration) — آخرین مرحله
- مورد #۷ (Notification/Feed) — آینده

---

## [2026-08-18] ریشه‌یابی ۴۹ خطای تست — ۴ ریشه واقعی

**نوع:** Bugfix + Infrastructure  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**تشخیص:** ۴۹ خطا (34 error + 15 failure) از ۴ ریشه می‌آمدند، نه ۴۹ مشکل جدا.

### ریشه ۱ — تاریخچه migration خراب (۳۴ خطا)
علائم: `no such column: tracks_album.is_public` ، `tracks_genre.name` ، `no such table: plays_pointledger` ، `plays_fraudflag.ip_hash`

علت: دو migration موازی با شماره 0010 در tracks، merge نادرست در 0012، و فیلدهایی که در مدل اعلام شده ولی هیچ migration معتبری آن‌ها را نساخته بود.

راه‌حل: `reset_migrations.ps1` — بازسازی کامل migration ها و دیتابیس از صفر (با پشتیبان‌گیری خودکار).

### ریشه ۲ — Middleware به API هم redirect می‌زد (۹ خطا) — **باگ واقعی production**
علائم: `302 != 200` ، `302 != 400` ، `302 != 405` در plays، moderation، tracks

علت: `OnboardingRequiredMiddleware` هر مسیری را به onboarding redirect می‌کرد — حتی `/api/v1/play/`. یعنی کاربری که onboarding نکرده، JS او به‌جای JSON یک صفحه HTML می‌گرفت و پخش می‌شکست.

راه‌حل: `accounts/middleware.py` بازنویسی شد — مسیرهای `/api/` دیگر redirect نمی‌شوند؛ به‌جای آن `403` با پیلود JSON و کلید `onboarding_required` برمی‌گردانند.

### ریشه ۳ — `interactions/admin.py` خالی بود (۱ خطا)
علائم: `/admin/interactions/comment/` → 404

راه‌حل: ثبت ۵ مدل (Comment، TrackLike، CommentLike، CreatorFollow، Favorite) با search_fields و autocomplete.

### ریشه ۴ — تست‌ها helper مشترک نداشتند
راه‌حل: `core/test_utils.py` ساخته شد — `make_user()`، `make_superuser()`، `login()`. از این به بعد همه تست‌ها کاربر را از اینجا بسازند تا مشکل onboarding تکرار نشود.

**فایل‌های تغییریافته:**
- `accounts/middleware.py` — بازنویسی کامل، API دیگر redirect نمی‌شود
- `interactions/admin.py` — ۵ مدل ثبت شد
- `core/test_utils.py` — جدید
- `core/tests_smoke.py` — جدید، ~۴۵ تست پوشش همه صفحات
- `.casset/TESTING.md` — راهنمای کامل تست خودکار و دستی
- `reset_migrations.ps1` — جدید

**درس معماری:** وقتی ۳۰+ خطا یک پیام یکسان دارند (`no such column`)، یک ریشه دارند — نه ۳۰ مشکل. همیشه پیام خطا را گروه‌بندی کن.

---

## [2026-08-17] مورد #۷ — سیستم Notification کامل ساخته شد

**نوع:** Architecture + Feature  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های ایجاد/تغییریافته:**
- `notifications/models.py` — مدل Notification، ۸ verb، groupable، persian_text()
- `notifications/services.py` — تمام منطق ساخت notification
- `notifications/signals.py` — ویرینگ خودکار به like/follow/comment/status
- `notifications/apps.py` — signal در ready()
- `notifications/views.py` — لیست HTML + API JSON + mark-read
- `notifications/urls.py` — ۳ endpoint
- `notifications/admin.py` — داشبورد read-only
- `notifications/tests.py` — ۴۲ تست
- `notifications/migrations/0001_initial.py`
- `templates/notifications/list.html` — صفحه اعلان‌ها (RTL، فارسی)
- `templates/base.html` — زنگ اعلان + badge قرمز + polling 60ث، لینک در sidebar
- `config/settings/base.py` — اضافه به INSTALLED_APPS
- `config/urls.py` — include
- `accounts/signals.py` — fix: create ← get_or_create (idempotent)
- `tracks/migrations/0010_move_book_fields_to_track.py` — no-op شد (migration خراب)

**۸ نوع notification:**
`new_follower` • `track_liked` • `track_comment` • `comment_liked` • `track_approved` • `track_rejected` • `new_track_from_follow` • `milestone_plays`

**معماری:**
- Append-only — حذف نمی‌شه، فقط read_at پر می‌شه
- Groupable — N لایک روی یک ترک → یک ردیف با actor_count (پنجره 24 ساعت)
- Signal-driven — viewها دست نخوردند
- هر signal handler در try/except — باگ notification هرگز action اصلی را نمی‌شکند

**باگ‌های کشف و حل‌شده حین تست:**
1. `accounts/signals.py` از `create` استفاده می‌کرد → IntegrityError در تمام تست‌ها
2. `tracks/migrations/0010_move_book_fields_to_track` → KeyError: 'book_format'
3. تست‌ها onboarding_complete نداشتند → middleware redirect می‌کرد (302)
4. `templates/notifications/list.html` وجود نداشت

**وضعیت CLAUDE.md:** مورد #۷ بسته شد ✅

**تنها مورد باقی‌مانده:** #۴ (Postgres migration)

---

## [2026-08-17] مورد #۳ — PointLedger و سیستم امتیاز حرفه‌ای ساخته شد

**نوع:** Architecture + Security  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `plays/models.py` — اضافه PointLedger، بهبود FraudFlag (ip_hash اضافه شد)
- `plays/services.py` — جدید: تمام منطق award در یک جا
- `plays/views.py` — ساده‌سازی: فقط HTTP و call به service
- `plays/admin.py` — جدید: dashboard کامل برای staff
- `plays/tests.py` — جدید: 18 تست برای تمام حالات
- `plays/management/commands/recalculate_points.py` — جدید

**معماری اصلی:**
- `UserProfile.points` کش درمی‌ماند ولی فقط کش است
- `PointLedger` منبع حقیقت است (SUM delta)
- هر تصمیم (award یا block) یک ردیف در لجر دارد
- blocked entries delta=0 — اودیت کامل بدون حذف داده

**چهار دروازه دفاعی:**
1. PlayEvent وجود داشته باشد (BLOCKED_NO_EVENT)
2. قبلاً award نشده باشد (BLOCKED_DUPLICATE)
3. زمان کافی گذشته باشد elapsed >= duration*0.5 (BLOCKED_TIME + FraudFlag)
4. IP روزانه بیشتر از 50 award نگرفته باشد (BLOCKED_IP_LIMIT + FraudFlag)

**وضعیت CLAUDE.md:** مورد #۳ بسته شد ✅

---

## [2026-08-17] مورد #۵ — pyproject.toml بازنویسی کامل

**نوع:** Config  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `pyproject.toml` — بازنویسی کامل با بخش‌بندی دقیق و comment
- `CLAUDE.md` — مورد #۵ بسته شد

**مشکلات حل‌شده:**
1. پکیج‌های واقعی (Pillow, DRF, django-filter, python-dotenv, tzdata) در `dependencies` نبودند
2. نسخه psycopg از `>=3.2` به `>=3.3` اصلاح شد (نسخه واقعی نصب‌شده)
3. `addopts` به `--tb=short` ارتقا یافت
4. `pytest-cov` برای coverage اضافه شد
5. `ruff` به عنوان linter اضافه شد (جایگزین flake8+isort)
6. `[tool.ruff]` با تنظیمات اختصاصی migrations و settings اضافه شد

**تصمیمات مهم:**
- `allauth` عمداً در dependencies نیست — در `requirements_current.txt` هست ولی در کدبیس هیچجا import نمی‌شه، پس آشغال‌زایندهاست
- transitive depها (asgiref, sqlparse, typing-extensions) عمداً حذف شدند

**اقدام بعدی:**
```powershell
pip install -e ".[dev]"
```

**وضعیت CLAUDE.md:** مورد #۵ بسته شد ✅

---

## [2026-08-16] مورد #۸ — سیستم SECRET_KEY کاملاً ایمن شد

**نوع:** Security + Config  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `config/settings/base.py` — تابع `_require_secret()` + حذف هر fallback ناامن + `DB_ENGINE` دو حالته + `context_processors` کامل + `STATIC_ROOT` + `OnboardingRequiredMiddleware`
- `config/settings/prod.py` — اضافه `import os` + ALLOWED_HOSTS validation + security headers کامل
- `config/settings/dev.py` — اضافه `import os` + EMAIL_BACKEND console + INTERNAL_IPS
- `config/settings.py` — رنج شد (با ImportError واضح)
- `config/wsgi.py` — `config.settings` → `config.settings.prod`
- `config/asgi.py` — `config.settings` → `config.settings.prod`
- `manage.py` — `config.settings` → `config.settings.dev`
- `pyproject.toml` — `DJANGO_SETTINGS_MODULE` → `config.settings.dev`
- `.gitignore` — `.env`، `staticfiles/`، `media/` اضافه شد
- `.env.example` — بازنویسی کامل با راهنمای واضح
- `CLAUDE.md` — مورد #۸ بسته شد

**مشکلات حل‌شده:**
1. `SECRET_KEY` fallback ناامن `"django-insecure-change-me"` — حذف شد
2. `PLAY_IP_SALT` / `PLAY_UA_SALT` fallback `"change-me-in-prod"` — حذف شد
3. `config/settings.py` قدیمی دارای `subscriptions` — retired شد
4. `wsgi.py` / `asgi.py` / `manage.py` به settings قدیمی اشاره می‌کردند — fix شد
5. `.env` در `.gitignore` نبود — اضافه شد
6. `prod.py` بدون `import os` — fix شد
7. `context_processors` ناقص در `base.py` — اضافه شد

**منطق امنیتی تابع `_require_secret()`:**
- prod (`DEBUG=False`): اگه env خالی باشد → `ImproperlyConfigured` — سرور بالا نمی‌آید
- dev (`DEBUG=True`): اگه env خالی باشد → `secrets.token_hex(48)` تولید + `warnings.warn` — کار می‌کند اما دایمی نیست

**وضعیت CLAUDE.md:** مورد #۸ بسته شد ✅

**اقدام بعدی لازم:**  
تیم باید `.env` بسازه و `DJANGO_SECRET_KEY`، `PLAY_IP_SALT`، `PLAY_UA_SALT` را با دستور زیر پر کند:
```
python -c "import secrets; print(secrets.token_hex(48))"
```

---

## [2026-08-16] مورد #۱ — Album سیستم کاملاً حرفه‌ای شد

**نوع:** Bugfix + Refactor + Security  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `tracks/forms.py` — cover validation (Pillow MIME + حجم 5MB)، content_type security guard، widget attrs
- `tracks/views.py` — اضافه `album_delete`، fix N+1 در `album_list` با `Count` annotate
- `tracks/urls.py` — مسیر `album_delete` اضافه شد
- `tracks/admin.py` — `TrackInline` داخل AlbumAdmin، `Tag` رجیستر، fieldsets برای Track
- `tracks/tests.py` — افزودن تست delete (3 تست)، cover MIME، title length، content_type guard
- `templates/tracks/albums.html` — hardcoded URL → `{% url %}`، دکمه حذف، `track_count` annotation
- `templates/tracks/album_create.html` — hardcoded URL → `{% url %}`

**مشکلات حل‌شده:**
1. باگ اصلی `kind` field — قبلاً fix شده بود، lock-in تست اضافه شد
2. بدون delete — اضافه شد (`@require_POST`، ownership check، ترک دست‌نخورده)
3. cover بدون validation — Pillow magic-byte check + 5MB limit
4. N+1 query در album list — `Count` annotate جایگزین `prefetch_related`
5. content_type بدون server-side guard — crafted POST رد می‌شه
6. hardcoded URL در template — تمام `{% url %}` شدند
7. Admin ناقص — inline tracks، is_public filter، Tag admin اضافه شد

**نکته‌های معماری:**
- `album_delete` فقط POST قبول می‌کند (405 برای GET)
- حذف آلبوم ترک‌ها را حذف نمی‌کند (on_delete=SET_NULL)
- Cover validation به filename یا Content-Type header اعتماد نمی‌کند

**وضعیت CLAUDE.md:** مورد #۱ بسته شد ✅

---

<!-- NEW ENTRIES ABOVE THIS LINE -->` اضافه کنه.

---

## [2026-08-15] ایجاد سیستم Changelog

**نوع:** Docs  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `.casset/state/changelog.md` — این فایل (ایجاد شد)
- `.casset/state/current.md` — اشاره به changelog اضافه شد

**تصمیم:**  
هر session جدید Claude هیچ حافظه‌ای از session قبل ندارد. تنها منبع context فایل‌های روی disk هستند. یک changelog ساختارمند لازم بود که هر تغییر معماری را با فایل‌های دقیق ثبت کند، دلیل تصمیم را نگه دارد، و به Claude بگوید از کجا شروع کند.

**اثر:**  
از این به بعد هر تغییر مهم اینجا ثبت می‌شود. Claude در session جدید این فایل را می‌خواند و می‌داند دقیقاً کجای پروژه است.

**وضعیت CLAUDE.md:** بدون تغییر (فقط docs اضافه شد)

---

## [2026-08-15] حذف کامل وابستگی به `subscriptions` — یکپارچه‌سازی در `billing`

**نوع:** Architecture  
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `accounts/models.py` — docstring متد `has_vip()` از اشاره به subscriptions پاک‌سازی شد
- `billing/tests.py` — docstring کلاس `HasVipTests` به‌روز شد
- `_deprecated/subscriptions/__init__.py` — comment "RETIRED — DO NOT IMPORT" اضافه شد
- `CLAUDE.md` — مورد #۲ از 🔴 به ✅، domain map آپدیت شد
- `.casset/state/current.md` — اشاره به changelog اضافه شد

**تصمیم:**  
دو مدل `Plan` موازی وجود داشت:
- `billing.Plan` — کامل، با Invoice، Transaction، PayoutRequest، تست دارد
- `subscriptions.Plan` — ساده، بدون Invoice، قدیمی‌تر، در `_deprecated/` بود

بررسی grep نشان داد هیچ reference زنده‌ای در کدبیس (خارج از `_deprecated/`) به `subscriptions` وجود ندارد. `billing` قبلاً هم از INSTALLED_APPS حذف شده بود. تصمیم گرفته شد `billing` رسماً تنها منبع حقیقت اعلام شود.

**اثر:**
- `subscriptions` در `_deprecated/` آرشیو شد — هیچ migration اجرا نمی‌شود
- `billing.Plan` + `billing.Invoice` تنها منبع VIP/plan state است
- `UserProfile.has_vip()` به Invoice نگاه می‌کند، نه به فلگ مستقیم `is_vip`
- `is_vip` و `vip_until` روی UserProfile به عنوان fast-path cache باقی ماندند (نه source of truth)

**وضعیت CLAUDE.md:** مورد #۲ بسته شد ✅

**نکته برای session بعد:**  
اگه سوالی درباره subscriptions بود — در `_deprecated/` آرشیو است، retired است، نباید import شود.

---

<!-- NEW ENTRIES ABOVE THIS LINE -->
