# CLAUDE.md — قوانین ثابت پروژه Casset

> این فایل به‌طور خودکار توسط Claude (در Claude Code / Claude Desktop) در ابتدای هر جلسه کاری روی این ریپازیتوری خونده می‌شه.
> **هدف این فایل:** اینکه هیچ‌وقت لازم نباشه پروژه، قوانین، یا وضعیت فعلی رو دوباره توضیح بدی. هر چت جدید که از داخل این پوشه (`D:\Casset.ir\casset-django`) با Claude شروع بشه، این فایل رو می‌بینه و کل زمینه رو داره.
>
> منبع کامل‌تر و مفصل‌تر: `.casset/execution/90-day-roadmap.md` (همین ریپو) و صفحه Notion "Casset — Project Brain v1.0".

---

## ۱. Casset چیست (و چه چیزی نیست)

Casset یک **پلتفرم ایرانی انتشار و کشف صدا/محتوا** است (پادکست، موسیقی، کتاب صوتی، ویدیو) با تمرکز روی:
- آمار پخش **قابل‌اعتماد** (نه واقعیت مصنوعی)
- ارتباط مداوم بین Creator و Listener (نه صرفاً یک صفحه دانلود/پخش ساده)
- مسیر آینده برای Reward/Monetization

**نکته حیاتی که باید همیشه در نظر گرفته بشه:** Casset صرفاً یک "وب‌سایت نمایش فایل صوتی" نیست. هدف نهایی، ساخت **عادت استفاده مداوم** (Retention) است — یعنی کاربر باید دلیلی داشته باشه که هر روز/هفته برگرده: دنبال‌کردن Creatorهای موردعلاقه، اطلاع از محتوای جدید، تعامل (کامنت/لایک)، و دیدن رشد آمار خودش (اگه Creator باشه). این یعنی **لایه‌ی اجتماعی و اعلان‌رسانی (Notifications/Activity Feed) بخشی جدایی‌ناپذیر از MVP است**، نه یک فیچر "بعداً اضافه می‌کنیم".

**چیزی که Casset نیست (فعلاً):** یک سیستم توصیه‌گر هوشمند، چت خصوصی، مارکت‌پلیس پیچیده پرداخت، یا زیرساخت توزیع‌شده (Microservices). این‌ها عمداً به بعد از MVP موکول شدن.

---

## ۲. اصول مهندسی غیرقابل مذاکره (از Constitution)

- **Modular Monolith.** بازنویسی (Rewrite) یا تبدیل به Microservices ممنوعه مگر با دلیل مستند و تایید صریح کاربر.
- منطق کسب‌وکار باید در لایه **Service/Domain** باشه، نه مستقیم در `views.py`.
- پیشرفت پخش (progress) که از سمت Client میاد، **به‌تنهایی هرگز اثبات یک پخش معتبر نیست.**
- تشخیص "Qualified Play" باید **سمت سرور** و قابل Audit باشه.
- امتیاز/جایزه باید از طریق `PointLedger` (دفتر تراکنش) ثبت بشه؛ `UserProfile.points` هرگز نباید مستقیم دستکاری بشه — این فقط یک مقدار مشتق‌شده/کش است.
- Counterها و Aggregateها (مثل `play_count`, `DailyTrackStat`) داده مشتق‌شده‌اند و باید قابل بازسازی از منبع اصلی باشن.
- محیط Production باید PostgreSQL و Object-Storage-compatible باشه (نه SQLite، نه فایل‌سیستم لوکال).
- **هیچ فیچر مهمی بدون تست خودکار «Done» نیست.**
- قبل از هر تغییر معماری بزرگ، باید این فایل و مستندات `.casset/` خونده بشه.

---

## ۳. وضعیت شناخته‌شده‌ی فعلی کدبیس (تا تاریخ آخرین بررسی: مرداد ۱۴۰۵)

این‌ها یافته‌های **تایید‌شده با خوندن کد واقعی** هستن، نه فرض. تا وقتی رفع نشدن، هر Agent/Claude باید قبل از کار روی بخش مرتبط، این‌ها رو در نظر بگیره:

| # | مشکل | فایل | وضعیت |
|---|---|---|---|
| 1 | ~~`AlbumForm` به فیلدهای `kind`/`is_public` ارجاع می‌ده که در مدل `Album` وجود ندارن (کرش فعال)~~ | — | ✅ حل‌شده — باگ `kind` رفع، cover validation (Pillow)، album_delete، N+1 fix، content_type guard، تست‌های کامل |
| 2 | ~~دو مدل `Plan` موازی و ناسازگار در `billing` و `subscriptions`~~ | — | ✅ حل‌شده — `subscriptions` به `_deprecated/` منتقل و از INSTALLED_APPS حذف شد؛ `billing` تنها منبع حقیقت است |
| 3 | ~~امتیاز مستقیم روی `UserProfile.points` نوشته می‌شه، نه از طریق Ledger~~ | — | ✅ حل‌شده — `PointLedger` ساخته شد، `services.py` تنها منبع تصمیم award، چهار دروازه دفاعی |
| 4 | ~~دیتابیس فعلی SQLite است؛ `prod.py` تنظیمات Postgres نداره با اینکه `psycopg` نصبه~~ | — | ✅ کاملاً حل‌شده (۲۰۲۶-۰۸-۲۰) — `DB_ENGINE=postgresql` در `base.py` هاردن شد (`CONN_HEALTH_CHECKS`, `OPTIONS.sslmode`, `connect_timeout`)؛ `prod.py` با `ImproperlyConfigured` فیل می‌کند اگر `DB_ENGINE≠postgresql` یا `DB_PASSWORD` خالی باشد. **اتصال زنده به یک PostgreSQL واقعی (نسخه ۱۶.۲) حالا واقعاً تست شد**: کل `migrate` (هر ۱۴ اپ) هم زیر `config.settings.dev` هم `config.settings.prod` روی یک دیتابیس تازه بدون خطا اجرا شد، و **کل ۳۴۳ تست پروژه روی همون Postgres واقعی (نه SQLite) pass شدن** — همون فرآیندی که موارد #۱۳ (`Sum(boolean)`) رو لو داد. جزئیات کامل در changelog. |
| 5 | ~~`pyproject.toml` با پکیج‌های واقعاً استفاده‌شده (`allauth`, `pillow`, `django-filter`, DRF) هماهنگ نیست~~ | — | ✅ حل‌شده — بازنویسی کامل با بخش‌بندی دقیق، ruff و pytest-cov اضافه شد |
| 6 | ~~تست خودکار عملاً صفر است~~ | — | ✅ حل‌شده — تست‌های accounts، plays، tracks، billing اضافه شد |
| 7 | ~~هیچ سیستم Notification / Activity Feed وجود نداره~~ | — | ✅ حل‌شده — اپ `notifications` با ۸ verb، grouping، signals، API و ۴۲ تست |
| 8 | ~~`SECRET_KEY`, `PLAY_IP_SALT`, `PLAY_UA_SALT` مقدار پیش‌فرض ناامن دارن و در صورت نبود env، بی‌صدا fallback می‌کنن~~ | — | ✅ حل‌شده — `_require_secret()` در prod به `ImproperlyConfigured` فیل می‌کند، در dev هشدار می‌دهد |
| 9 | ~~`interactions/urls.py` فقط دو endpoint داشت (`toggle_like`, `toggle_follow`)~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۱۹) — `interactions/services.py` جدید + ۴ endpoint اضافه شد: `comment_add`, `comment_delete`, `comment_like`, `toggle_favorite`. کامنت گزارش‌پذیر است و بعد از ۳ گزارش خودکار مخفی می‌شود (`moderation/services.py::check_and_auto_hide_comment`). ۴۳ تست جدید (interactions ۳۶ + moderation ۷). |
| 10 | ~~پلیر فعلی سرعت پخش/Resume/Sleep Timer نداشت~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۱۹) — `static/app.js`: کنترل سرعت (۰.۵x–۲x، ذخیره در localStorage)، Resume Position به‌ازای هر ترک، Sleep Timer با پله‌های ۱۵/۳۰/۴۵/۶۰ دقیقه. دکمه‌های `#pbSpeed`/`#pbSleep` در playerbar (`templates/base.html`). دستی در مرورگر تایید شد. |
| 11 | ~~staff هیچ اکشنی روی Report نداشت (فقط لیست می‌دید، نمی‌تونست reviewed/actioned بزنه) و هیچ مکانیزم تعلیق حساب کاربری وجود نداشت~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۱۹، فاز ۳) — `moderation/services.py::update_report_status/suspend_user/unsuspend_user` + دکمه‌های اکشن در `report_queue.html`. تعلیق از طریق `User.is_active` استاندارد جنگو اعمال می‌شود؛ **مهم:** ورود با OTP از این چک صرف‌نظر می‌کرد (`django.contrib.auth.login()` خودش `is_active` را چک نمی‌کند) — در `phone_verify_view` صریحاً اضافه شد. |
| 12 | ~~`check_and_notify_milestone` (اعلان ۱۰۰/۵۰۰/... پخش) نوشته شده بود ولی هیچ‌جا صدا زده نمی‌شد — کد مرده~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۱۹، فاز ۳) — در `plays/views.py::register_play` بعد از هر افزایش واقعی `play_count` صدا زده می‌شود. |
| 13 | ~~`accounts/views.py::creator_studio_view` با `Sum("point_awarded")` روی یک `BooleanField` جمع می‌زد — روی SQLite بی‌صدا کار می‌کنه ولی روی PostgreSQL خطای `function sum(boolean) does not exist` می‌ده~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۲۰، فاز ۴+۵) — با `Count("id", filter=Q(point_awarded=True))` جایگزین شد؛ قابل‌حمل بین دیتابیس‌ها. کشف‌شده حین ممیزی کد قبل از ساخت روی همین view. |
| 14 | ~~همون view: `my_tracks = list(qs)[:50]` — کل ترک‌های Creator رو (بدون LIMIT در SQL) به لیست پایتون تبدیل می‌کرد، بعد ۵۰ تای اول رو می‌گرفت~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۲۰، فاز ۴+۵) — به `list(qs[:50])` تغییر کرد؛ `LIMIT 50` حالا در سطح SQL اجرا می‌شود. |

> وقتی هرکدوم از این موارد رفع شد، این جدول باید در همین فایل آپدیت بشه (ردیف حذف یا وضعیت به ✅ تغییر کنه).

---

## ۴. نقشه دامنه‌ها (Domain Map) — وضعیت فعلی

| اپ | نقش | بلوغ فعلی |
|---|---|---|
| `accounts` | کاربر، پروفایل، OTP، آنبوردینگ Creator، تعلیق حساب، آنالیتیکس Creator | متوسط — منطق VIP در مدل پخش شده، باید جمع بشه. تعلیق حساب (`is_active` + `UserProfile.suspended_at/reason`) روی هر دو مسیر ورود اعمال می‌شود. `creator_studio_view` حالا شنونده اول‌بار/برگشتی + عملکرد هر ترک را نشان می‌دهد (فاز ۴+۵) |
| `tracks` | آلبوم/ترک، ژانر، تگ، چرخه انتشار | ✅ خوب — AlbumForm حرفه‌ای شد، cover validation، CRUD کامل، تست دارد |
| `uploads` | آپلود فایل، ارسال برای بررسی | نیاز به Service مجزا برای اعتبارسنجی فایل؛ `submit_track` حالا `PlatformSetting.auto_approve_tracks` را چک می‌کند (فاز ۳) |
| `plays` | ثبت پخش، آمار روزانه، Fraud signal، اعلان نقطه‌عطف | ✅ خوب — PointLedger، ۴ دروازه امنیتی، services.py، recalculate_points، `check_and_notify_milestone` حالا واقعاً صدا زده می‌شود. `aggregate_stats`/`DailyTrackStat` آماده‌اند ولی عمداً به هیچ داشبوردی وصل نشدند (بخش ۹ روadmap) |
| `interactions` | لایک، فالو، علاقه‌مندی، کامنت، بلاک کامنت‌گذار | ✅ کامل — مدل + endpoint هر شش نوع تعامل (like/follow/comment/comment-like/favorite/block) با `services.py`، همه به Notification وصل، ۴۲ تست |
| `explore` | کشف، فید شخصی‌سازی‌شده، Trending، پیشنهاد Creator | ✅ کامل شد (۲۰۲۶-۰۸-۲۰، فاز ۴+۵) — `discover_view` حالا فید بر اساس Follow، Trending وزن‌دار به Qualified Play، و پیشنهاد Creator داره؛ ۱۶ تست جدید (قبلاً صفر) |
| `moderation` | گزارش، AuditLog، صف بررسی ترک، اکشن staff | ✅ کامل‌تر شد — تایید/رد ترک (`approve_track`/`reject_track` حالا در `services.py`، به‌اشتراک با auto-approve)، گزارش کامنت + مخفی‌سازی خودکار، **و حالا** staff می‌تواند وضعیت Report را عوض کند، کامنت مخفی‌شده را برگرداند، و حساب تعلیق/رفع‌تعلیق کند |
| `billing` | پلن، فاکتور، تراکنش، درخواست تسویه | تنها منبع حقیقت برای VIP/پلن — تمیز و دارای تست |
| ~~`subscriptions`~~ | ~~پلن و اشتراک (نسخه قدیمی‌تر)~~ | ✅ حذف‌شده — در `_deprecated/` آرشیو شده، هیچ referenceای در کد زنده وجود ندارد |
| `core` | تنظیمات پلتفرم (Singleton) | خوب |
| **(جدید - وجود دارد)** | Notification / Activity Feed | ✅ کامل — ۸ verb، grouping 24ساعته، signal-driven، API + HTML، ۴۲ تست |

---

## ۵. نحوه‌ی کار Claude روی این پروژه

**اول از همه در هر session:**
1. این فایل (CLAUDE.md) رو بخوان
2. `.casset/state/changelog.md` رو بخوان — تاریخچه دقیق همه تغییرات معماری اینجاست
3. `.casset/state/current.md` رو بخوان — وضعیت sprint فعلی

بعد از خوندن این سه فایل، دقیقاً می‌دونی کجای پروژه‌ای و چه تغییراتی قبلاً انجام شده.

**قوانین کار:**
1. **بازنویسی ممنوع.** هر تغییری باید افزایشی (Incremental) و روی پایه‌ی موجود باشه.
2. **کد بدون تست = کار ناتمام.** هر فیچر یا Fix مهم باید تست خودکار همراه داشته باشه (pytest + pytest-django طبق `pyproject.toml`).
3. **Scope Creep ممنوع.** ایده‌های جدید (چت خصوصی، توصیه‌گر هوشمند، ...) نباید بدون تایید صریح کاربر وارد کار جاری بشن؛ به بخش Icebox در Notion منتقل بشن.
4. **قبل از تغییر معماری بزرگ، از کاربر تایید گرفته بشه** — این‌ها معمولاً تصمیم محصولی هم هستن، نه فقط فنی.
5. کاربر (صاحب پروژه) به پایتون آشناست ولی نقشش عمدتاً **Review و تست** است، نه نوشتن کد. توضیحات باید برای این سطح باشه: نه خیلی مقدماتی، نه فرض دانش عمیق Django framework internals.
6. بعد از هر تغییر مهم، **دو جا** آپدیت بشه: جدول بخش ۳ همین فایل + `.casset/state/changelog.md`.
7. زبان پیش‌فرض ارتباط با کاربر: **فارسی.** کد، نام متغیر، commit message: انگلیسی.

---

## ۶. مسیر فعلی (خلاصه) — جزییات کامل در `.casset/execution/90-day-roadmap.md`

```
فاز ۱  (روز ۱-۱۴)   تثبیت پایه: رفع ۸ مورد بخش ۳، اولین تست‌ها، Postgres — ✅ بسته شد (۲۰۲۶-۰۸-۱۹)
فاز ۲  (روز ۱۵-۳۸)  بازنگری‌شده — ✅ بسته شد (۲۰۲۶-۰۸-۱۹): موارد #۹/#۱۰ رفع شدند (کامنت/لایک‌کامنت/
                    Favorite + Player UX رقابتی). جزئیات کامل: `.casset/execution/90-day-roadmap.md` بخش ۷
فاز ۳  (روز ۳۹-۴۹)  اعتماد و امنیت (Trust & Safety) — ✅ بسته شد (۲۰۲۶-۰۸-۱۹): موارد #۱۱/#۱۲ رفع شدند
                    (اکشن staff روی Report، تعلیق حساب، بلاک کامنت‌گذار، auto-approve، اعلان نقطه‌عطف).
                    جزئیات کامل: `.casset/execution/90-day-roadmap.md` بخش ۸
فاز ۴+۵ (ادغام‌شده) فید شخصی + آنالیتیکس + کشف هوشمند — ✅ بسته شد (۲۰۲۶-۰۸-۲۰): موارد #۱۳/#۱۴ رفع
                    شدند. Follow-feed/Trending وزن‌دار/پیشنهاد Creator/آنالیتیکس Creator تکمیل و تست شد.
                    جزئیات کامل: `.casset/execution/90-day-roadmap.md` بخش ۹
فاز ۶  (روز ۸۵-۹۰)  سخت‌سازی Production و استقرار نهایی
```

سند کامل شامل جزییات هر فاز، معیار "Done" هر بخش، و ریسک‌های هر مرحله در فایل زیر است:
**`.casset/execution/90-day-roadmap.md`**

---

## ۷. دستورات توسعه (Development Commands)

راه‌اندازی اولیه:
```powershell
pip install -e ".[dev]"
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

تست (pytest-django روی `config.settings.dev` تنظیم شده — در `pyproject.toml`):
```powershell
python manage.py test                          # کل پروژه
python manage.py test accounts                 # فقط یک اپ (tracks, plays, billing, notifications, ...)
python manage.py test core.tests_smoke -v 2     # smoke test همه صفحات — مهم‌ترین تست، هر تغییر بزرگ را با این چک کن
python manage.py test accounts.tests.SomeClass.test_method   # یک تست خاص
pytest accounts/tests.py::SomeClass::test_method             # معادل با pytest
pytest --cov=. --cov-report=html                # پوشش تست → htmlcov/index.html
```
چک‌لیست کامل تست دستی/سناریوهای E2E مرورگر: `.casset/TESTING.md`.

بررسی سلامت پروژه (قبل از هر commit مهم اجرا شود):
```powershell
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
ruff check .
```

Migration:
```powershell
python manage.py makemigrations <app_name>
python manage.py migrate
```

نکته تنظیمات: `manage.py` و `pyproject.toml` هر دو پیش‌فرض `DJANGO_SETTINGS_MODULE=config.settings.dev` دارند. برای prod باید `config.settings.prod` صراحتاً ست بشه و `DJANGO_SECRET_KEY`, `PLAY_IP_SALT`, `PLAY_UA_SALT` واقعی وجود داشته باشن — وگرنه استارت‌آپ با `ImproperlyConfigured` فیل می‌کنه (عمدی، طبق مورد ۸ بخش ۳). سوییچ دیتابیس با `DB_ENGINE=sqlite|postgresql` در `.env`.

---

## ۸. معماری کد (Architecture Map)

- **Modular monolith با یک اپ Django به‌ازای هر دامنه.** لیست واقعی و فعال اپ‌ها همیشه از `config/settings/base.py::INSTALLED_APPS` بخون، نه از مستندات — این فایل منبع حقیقت است: `accounts`, `tracks`, `uploads`, `plays`, `interactions`, `playlists`, `explore`, `moderation`, `billing`, `notifications`, `core`.
- **Settings سه‌لایه:** `config/settings/base.py` (مشترک) ← `dev.py` / `prod.py` این را extend می‌کنن. فایل تخت قدیمی `config/settings.py` دیگر روی دیسک وجود ندارد — کاملاً حذف شده (commit `ea1d08b`، تایید مجدد توسط یک اجرای خودکار در ۲۰۲۶-۰۸-۲۰)، نه صرفاً بلاک‌شده با `raise ImportError` (که توصیف قدیمی این خط بود). هیچ import فعالی به `config.settings` (بدون `.dev`/`.prod`) در کدبیس وجود ندارد.
- **Routing تخت:** هر اپ `urls.py` خودش را دارد و در `config/urls.py` بدون prefix با `include()` مونت می‌شود. الگوی `<slug:handle>/` (پروفایل عمومی) عمداً آخرین pattern است — هر URL جدید باید **قبل از آن** در `config/urls.py` یا در `urls.py` یکی از اپ‌ها اضافه بشه، وگرنه این الگو مسیر جدید رو قورت می‌ده.
- **لایه Service/Domain** طبق قانون بخش ۲ باید منطق کسب‌وکار رو از `views.py` جدا نگه داره؛ فعلاً فقط `plays/services.py` و `notifications/services.py` این الگو را کامل پیاده کرده‌اند (نمونه‌ی مرجع برای سرویس جدید). بقیه‌ی اپ‌ها (`accounts`, `tracks`, `billing`, ...) هنوز بخشی از منطق را مستقیم در `views.py` دارند — وقتی منطق غیرپیش‌پاافتاده به یکی از این اپ‌ها اضافه می‌کنی، آن را در یک ماژول `services.py` مشابه بنویس، نه مستقیم در view.
- **گراف اصلی کسب‌وکار:** User → Creator (`accounts`) → Track/Album (`tracks`) → PlaybackSession/Event → QualifiedPlay (`plays`) → `PointLedger` (`plays/models.py`, نوشتن فقط از طریق `plays/services.py`) → Notification (`notifications`, signal-driven از `notifications/signals.py`) → Dashboard/Analytics.
- **بدون فرانت‌اند بیلد جدا.** `static/app.js` + `static/app.css` دستی نوشته شدن (بدون bundler/`package.json`)؛ رندر سمت سرور با Django templates در `templates/`.
- **`_deprecated/`** شامل `subscriptions` و `templates_subscriptions` آرشیوشده است — هرگز به آن‌ها ارجاع نده یا به `INSTALLED_APPS` برنگردون؛ `billing` تنها منبع حقیقت پلن/اشتراک است.
- فایل‌های `db.sqlite3.backup*` در ریشه‌ی ریپو snapshotهای دستی محلی‌اند، نه بخشی از schema رسمی یا migration — نادیده بگیر مگر کاربر صراحتاً بهشون اشاره کنه.
