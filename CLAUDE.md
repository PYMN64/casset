# CLAUDE.md — قوانین ثابت پروژه Casset

> این فایل به‌طور خودکار توسط Claude (در Claude Code / Claude Desktop) در ابتدای هر جلسه کاری روی این ریپازیتوری خونده می‌شه.
> **هدف این فایل:** اینکه هیچ‌وقت لازم نباشه پروژه، قوانین، یا وضعیت فعلی رو دوباره توضیح بدی. هر چت جدید که از داخل این پوشه (`D:\Casset.ir\casset-django`) با Claude شروع بشه، این فایل رو می‌بینه و کل زمینه رو داره.
>
> منبع کامل‌تر و مفصل‌تر: `.casset/execution/90-day-roadmap.md` (همین ریپو) و صفحه Notion "Casset — Project Brain v1.0".

> **نسخه‌ی مبنا (Baseline) فعلی: `v1.2.0`** (تگ گیت‌هاب، commit `f396b3c`، ثبت‌شده ۲۰۲۶-۰۸-۲۰) —
> اولین نسخه‌ی کاملاً قابل‌استقرار بعد از بازبینی جامع «فاز حرفه‌ای» (پلیر/پروفایل/آپلود/داشبورد ادمین).
> بدون فرانت‌اند بیلد جدا (Django templates + `static/app.js` دستی)، ۵۰۲ تست سبز (SQLite) + ۵۰۳ تست
> سبز (PostgreSQL واقعی)، `ruff` تمیز. **هر تغییر بعدی روی این تگ اعمال می‌شه** — قبل از هر کار جدید،
> `git log`/`git tag` رو چک کن تا مطمئن بشی روی همین baseline یا جلوتر از اون هستی، نه یک commit قدیمی‌تر.
> جزئیات کامل: `.casset/state/changelog.md` (entry «فاز حرفه‌ای») و `.casset/state/current.md`.
> **توجه:** چند تگ محلی قدیمی/ناهماهنگ (`v.2.0.0`, `v1.1.0`, `v1.1.0-stabilization`, `v2`, `v2-safe`) از
> جلسات قبلی روی دیسک هستن که هیچ‌وقت push نشدن و به این خط تاریخچه‌ی خطی مربوط نیستن — نادیده بگیر؛
> فقط تگ‌های `vX.Y.Z` که در `git ls-remote --tags origin` هم هستن معتبرن.

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
| 15 | ~~`core/staff_urls.py` (users/creators console + creator_detail) از قبل روی دیسک بود ولی هیچ‌وقت در `config/urls.py` با `include()` مونت نشده بود — کل پنل staff غیرقابل‌دسترس بود~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۲۰، فاز نهایی) — مونت شد در `staff/`؛ صفر تست قبلی به ۱۵+ تست رسید. |
| 16 | ~~`core/staff_views.py::users_console` هم دقیقاً همون باگ مورد #۱۳ رو داشت (`Sum("...point_awarded")` روی BooleanField) — چون این view تا همین فاز غیرقابل‌دسترس بود، هیچ‌وقت لمس نشده بود~~ | — | ✅ حل‌شده — با `Count(..., filter=Q(...=True))` جایگزین شد؛ **با اجرای زنده روی PostgreSQL واقعی لو رفت**، دقیقاً همون فرآیندی که #۱۳ رو کشف کرد. |
| 17 | ~~`billing/views.py::create_payout_request` هیچ‌وقت امتیاز کاربر رو کم نمی‌کرد — بعد از تایید یک payout، همون امتیاز باز هم قابل درخواست مجدد بود~~ | — | ✅ حل‌شده — `PayoutRequest.points` (فیلد جدید) + `billing/services.py::approve_payout` امتیاز رو از طریق `PointLedger` (delta منفی، reason=`PAYOUT_DEDUCTION`) کسر می‌کنه، نه دستکاری مستقیم `UserProfile.points`. |
| 18 | ~~`accounts/forms.py::ProfileSettingsForm` هیچ `clean_cover`/`clean_avatar` نداشت — برخلاف Track/Album، آپلود avatar/cover پروفایل بدون اعتبارسنجی MIME/سایز رد می‌شد~~ | — | ✅ حل‌شده — از همون `core/validators.py::validate_image` مشترک استفاده می‌کنه. |
| 19 | ~~`templates/accounts/public_profile.html` یک قالب orphan بود — هیچ view‌ای رندرش نمی‌کرد (`public_profile`/`public_profile_by_handle` هر دو از `public_profile_pro.html` استفاده می‌کنن)~~ | — | ✅ حذف شد (همون الگوی حذف `templates/tracks/detail.html` در فاز ۳). |
| 20 | ~~`accounts/views.py::phone_start_view` کد OTP رو در production عملاً به هیچ‌کجا ارسال نمی‌کرد — فقط `messages.success(request, "کد ارسال شد")` می‌گفت بدون اینکه واقعاً SMS بره~~ | — | ✅ حل‌شده (فاز نهایی) — `accounts/services.py` provider abstraction (Kavenegar واقعی / Console برای dev)؛ prod بدون `KAVENEGAR_API_KEY` واقعی اصلاً بالا نمی‌آد. |
| 21 | ~~**باگ بحرانی:** الگوی URL `t/<slug:slug>/` از converter داخلی `slug` جنگو استفاده می‌کرد که فقط ASCII می‌پذیره (`[-a-zA-Z0-9_]+`)، ولی `Track.save()` با `slugify(allow_unicode=True)` اسلاگ فارسی می‌سازه — یعنی **صفحه‌ی هر ترک با عنوان فارسی کاملاً غیرقابل‌دسترس بود** و `{% url 'track_detail' %}` خطای `NoReverseMatch` می‌داد~~ | — | ✅ حل‌شده (۲۰۲۶-۰۸-۲۰) — `core/converters.py::UnicodeSlugConverter` (رجیستر شده به‌عنوان `uslug` در `config/urls.py`). چون همه‌ی تست‌های قبلی عنوان انگلیسی داشتن، این باگ هیچ‌وقت لو نرفته بود؛ ۴ تست رگرسیون با عنوان فارسی اضافه شد (`tracks/tests.py::PersianSlugRoutingTests`). |
| 22 | ~~`config/settings/__init__.py` یک `from .dev import *` داشت — یعنی `DJANGO_SETTINGS_MODULE=config.settings` (بدون `.dev`/`.prod`) بی‌صدا تنظیمات **dev** رو لود می‌کرد: `DEBUG=True`، کوکی ناامن، SQLite، و SECRET_KEY تصادفی — روی یک سرور production فاجعه‌ی خاموش~~ | — | ✅ حل‌شده — حالا اگر `DJANGO_SETTINGS_MODULE` دقیقاً `config.settings` باشه، `ImportError` صریح می‌ده. شرطی نوشته شده (نه `raise` بی‌قید) چون پایتون قبل از زیرماژول، پکیج والد رو import می‌کنه و `raise` بی‌قید مسیر سالم `config.settings.dev` رو هم می‌شکست. |
| 23 | ~~OG image در `track_detail.html` و `public_profile_pro.html` با `{{ request.scheme }}://{{ request.get_host }}{{ ...url }}` ساخته می‌شد — با `USE_S3_STORAGE=1` که `FileField.url` خودش مطلقه، URL خراب دوتایی (`https://casset.ir/https://bucket...`) تولید می‌کرد~~ | — | ✅ حل‌شده — `core/templatetags/casset_urls.py::abs_url` که از `request.build_absolute_uri()` استفاده می‌کنه (URL مطلق رو دست‌نخورده می‌ذاره، نسبی رو prefix می‌کنه). |
| 24 | ~~۳ قالب یتیم (`accounts/creator_dashboard.html`, `playlists/index.html`, `tracks/artist_profile.html`) که هیچ view‌ای رندرشون نمی‌کرد — `artist_profile` فقط `redirect` می‌کنه و هرگز قالبش رو render نمی‌کنه~~ | — | ✅ حذف شدند (همون الگوی موارد #۱۹ و فاز ۳). |
| 25 | ~~۴ مدل (`playlists.Playlist`, `playlists.PlaylistItem`, `explore.FeaturedPin`, `moderation.AuditLog`) در پنل ادمین ثبت نشده بودن — یعنی ادمین نمی‌تونست پین‌های تبلیغاتی صفحه‌ی کشف رو مدیریت کنه یا رد حسابرسی رو ببینه~~ | — | ✅ حل‌شده — هر ۲۵ مدل پروژه حالا در ادمین ثبت‌شده‌ان. `AuditLog` عمداً **فقط-خواندنی**ه (add/change/delete هر سه رد می‌شن) چون قابل‌ویرایش بودنِ رد حسابرسی کل هدفش رو از بین می‌بره. |
| 26 | ~~`#plModal` (افزودن به پلی‌لیست) و `#qPanel` (صف پخش) کاملاً در JS پیاده‌سازی شده بودن (`plModalOpen`, `qPanelOpen`, ...) ولی هیچ‌جای `templates/` این المان‌ها وجود نداشتن — یعنی دکمه‌ی «＋ پلی‌لیست» و «Queue» در نوار پخش، در سایت واقعی هیچ کاری نمی‌کردن (silent no-op، بدون خطای قابل‌مشاهده)~~ | — | ✅ حل‌شده (فاز دوم) — هر دو overlay panel + یک `#embedModal` جدید به `templates/base.html` اضافه شدن، با CSS مشترک `.overlay-panel`. تایید دستی end-to-end در مرورگر: افزودن به پلی‌لیست و صف پخش هر دو الان واقعاً کار می‌کنن. |
| 27 | ~~`playlists/views.py::library_view` کوئری‌ست `playlists` رو بدون `annotate(item_count=...)` می‌ساخت، ولی `library.html` از `{{ p.item_count }}` استفاده می‌کرد — همیشه خالی رندر می‌شد (فقط `api_playlist_mine`، که برای مودال JS استفاده می‌شه، این annotate رو داشت). `templates/playlists/playlist_detail.html` هم `{{ playlist.name }}` رو رندر می‌کرد در حالی که context key واقعی `pl` بود — نام پلی‌لیست هیچ‌وقت در صفحه‌ی خودش نشون داده نمی‌شد~~ | — | ✅ حل‌شده — annotate اضافه شد، template به `pl` اصلاح شد، هر دو صفحه به فارسی و به فرم AJAX (هماهنگ با بقیه‌ی سایت) بازنویسی شدن. تست‌های رگرسیون: `playlists/tests.py` (قبلاً کاملاً خالی). |
| 28 | ~~`tracks/views.py::track_detail` کلید context `can_download` رو هیچ‌وقت ست نمی‌کرد در حالی که template با `{% if can_download %}` دکمه‌ی دانلود رو نشون می‌داد — یعنی دکمه‌ی دانلود VIP هیچ‌وقت، برای هیچ کاربری، دیده نمی‌شد~~ | — | ✅ حل‌شده — `can_download = bool(track.audio) and request.user.profile.has_vip()` اضافه شد؛ تست رگرسیون `CanDownloadRegressionTests`. |
| 29 | ~~نیمی از تمپلیت‌ها `data-cover` رو به‌صورت HTML خام (`<img src='...' />`) می‌ساختن و نیمی دیگه (`discover.html`) فقط URL خام — `app.js` این مقدار رو مستقیم `innerHTML` می‌کرد، یعنی روی نیمی از صفحات (پخش از discover) کاور پلیربار به‌جای عکس، متن خام URL نشون می‌داد~~ | — | ✅ حل‌شده (فاز حرفه‌ای) — قرارداد یکسان شد: `data-cover` همیشه فقط URL خام. `openPlayerBar`/`buildQueueFromContext` در `app.js` حالا از `element.style.backgroundImage` استفاده می‌کنن، نه `innerHTML` — امن‌تر هم هست (تزریق HTML از data attribute حذف شد). ۷ تمپلیت + `explore/views.py::api_station` اصلاح شدن. |
| 30 | ~~پروفایل عمومی: دکمه‌ی لایک (♥) فقط `data-like` داشت بدون `data-track` — `handleLike()` در app.js با `data-track` کار می‌کنه، پس کلیک روی این دکمه silent no-op بود. دکمه‌ی «＋ افزودن به صف» فقط `data-queue="{{ t.id }}"` داشت بدون data-src/title/by — و اصلاً هیچ click handler ای برای `[data-queue]` در کل پروژه وجود نداشت~~ | — | ✅ حل‌شده — `data-track` اضافه شد؛ `handleAddToQueue()` جدید در `app.js` + `[data-queue]` هندلر در دلیگیشن کلیک، حالا در همه‌ی تمپلیت‌های `data-queue` (discover/profile) کار می‌کنه. |
| 31 | ~~`playlists/views.py::playlist_detail` فقط برای `owner=request.user` کار می‌کرد (`@login_required` + فیلتر owner) — یعنی هیچ پلی‌لیست عمومی (`is_private=False`) اصلاً هیچ‌وقت برای کسی جز صاحبش قابل‌دیدن نبود، با اینکه UI (کتابخانه) گزینه‌ی «عمومی» رو نشون می‌داد~~ | — | ✅ حل‌شده — `playlist_detail` حالا owner همیشه، بقیه فقط اگر `is_private=False` (دقیقاً الگوی `track_detail`/`show_detail`)؛ `is_owner` به context اضافه شد تا دکمه‌های ویرایش/حذف فقط برای صاحب نشون داده بشن. |
| 32 | ~~`plays/utils.py::get_client_ip` فقط `REMOTE_ADDR` رو می‌خوند — پشت هر CDN/reverse-proxy واقعی همه‌ی بازدیدکننده‌ها یک IP می‌شدن و کل منطق ضد-تقلب IP-based (کلاهک روزانه، dedup) عملاً از کار می‌افتاد. `PlayEvent` uniqueness هم شامل `user` نبود — دو کاربر متفاوت پشت یک IP/NAT در یک روز فقط یک PlayEvent می‌گرفتن (دومی silently drop می‌شد)~~ | — | ✅ حل‌شده — `TRUST_PROXY_HEADERS` (env، پیش‌فرض خاموش) برای فعال‌سازی امن `X-Forwarded-For` پشت پراکسی قابل‌اعتماد؛ `PlayEvent` uniqueness به `(track, user, ip_hash, day_key)` تغییر کرد (migration جدید) + `services.py` گیت اول رو با `user=listener_user` هم فیلتر می‌کنه. ۵ تست رگرسیون جدید. |
| 33 | ~~پلیر global (`playerbar`) کنترل صدا (volume/mute)، نوار پیشرفت زمانی (seek قابل لمس/کیبورد)، دکمه‌ی skip ±۱۰ ثانیه، shortcut صفحه‌کلید، و reorder صف نداشت — روی موبایل (که waveform مخفیه) اصلاً هیچ راهی برای seek کردن وجود نداشت~~ | — | ✅ حل‌شده (فاز حرفه‌ای) — اسکرابر native range همیشه‌نمایان (لمس/کیبورد رایگان)، volume popover، skip ±۱۰، shortcutهای کامل (space/arrows/m/n/p)، reorder صف با ▲▼، و یک نمای «Now Playing» تمام‌صفحه جدید (`#npView`). |
| 34 | ~~`templates/staff/creator_detail.html` به `t.publish_at` ارجاع می‌داد که روی مدل `Track` اصلاً وجود نداره (فیلد واقعی `published_at` است) — ستون «انتشار» در پنل staff همیشه خالی بود~~ | — | ✅ حل‌شده — به `published_at` اصلاح شد؛ کل صفحه هم‌زمان به تم تیره‌ی سایت (به‌جای رنگ‌های hardcoded روشن `#eee`/`#fafafa`) بازطراحی شد. |

> وقتی هرکدوم از این موارد رفع شد، این جدول باید در همین فایل آپدیت بشه (ردیف حذف یا وضعیت به ✅ تغییر کنه).

---

## ۴. نقشه دامنه‌ها (Domain Map) — وضعیت فعلی

| اپ | نقش | بلوغ فعلی |
|---|---|---|
| `accounts` | کاربر، پروفایل، OTP (SMS واقعی)، آنبوردینگ Creator، تعلیق حساب، آنالیتیکس + درآمد Creator، **نشان تایید‌شده** | ✅ خوب — `accounts/services.py` جدید: provider abstraction برای OTP SMS (Kavenegar واقعی / Console dev). `creator_studio_view`/`creator_studio.html` حالا علاوه بر شنونده اول‌بار/برگشتی، یک بخش شفاف «موجودی + تراکنش‌های اخیر PointLedger + سوابق payout» هم داره. `UserProfile.is_verified` (فاز دوم) — بج اعتماد staff-only، از طریق `moderation/services.py::set_verified` + دکمه در `staff:creator_detail`. |
| `tracks` | آلبوم/ترک، ژانر، تگ، چرخه انتشار، **پادکست (Show/RSS)، waveform واقعی، Embed** | ✅ کامل (فاز دوم) — `Album` با `content_type=podcast` به‌عنوان «Show» بازاستفاده شد (بدون مدل جدید): `show_detail` + `feeds.py::ShowRSSFeed` (RSS استاندارد با namespace itunes — پیش‌نیاز واقعی توزیع در اپل/گوگل پادکست). `audio_processing.py` با `soundfile` (بدون نیاز به ffmpeg سیستمی) peak واقعی صدا استخراج می‌کنه، از طریق Celery (`tasks.py::generate_waveform_task`) حین آپلود؛ پلیربار الان یک waveform واقعی قابل‌کلیک/seek داره، نه فقط تزئینی. `track_embed` یک صفحه‌ی مینیمال برای `<iframe>` بیرون از سایت است (`@xframe_options_exempt`). **فاز حرفه‌ای:** خودسرویس Unpublish/Publish (`toggle_track_visibility`، بدون فیلد جدید — از `Visibility.PRIVATE` موجود استفاده می‌کنه). |
| `uploads` | آپلود فایل، ارسال برای بررسی | ✅ کامل شد (فاز حرفه‌ای) — `static/upload.js` جدید: drag & drop روی input واقعی، اعتبارسنجی کلاینت (پسوند/حجم) قبل از ارسال، تشخیص خودکار مدت‌زمان صوت در مرورگر (`HTMLAudioElement`)، پیش‌نمایش کاور، و progress bar واقعی با XHR (نه صرفاً غیرفعال‌کردن دکمه). اعتبارسنجی سرور (`clean_audio`/`clean_cover`) دست‌نخورده و همچنان مرجع نهایی است. |
| `plays` | ثبت پخش، آمار روزانه، Fraud signal، اعلان نقطه‌عطف | ✅ کامل شد (فاز حرفه‌ای) — PointLedger (با `PAYOUT_DEDUCTION` به‌عنوان delta منفی)، ۴ دروازه امنیتی، services.py، recalculate_points. **سخت‌سازی امنیتی:** `TRUST_PROXY_HEADERS` (env-gated) برای `X-Forwarded-For` پشت پراکسی قابل‌اعتماد؛ `PlayEvent` uniqueness حالا شامل `user` (دو کاربر پشت یک IP دیگه با هم تداخل نمی‌کنن). `aggregate_stats`/`DailyTrackStat` هنوز به هیچ داشبوردی وصل نشدن (خود پلی‌های روزانه مستقیماً از `PlayEvent` در `platform_dashboard` محاسبه می‌شن، نه از این جدول pre-aggregate). |
| `interactions` | لایک، فالو، علاقه‌مندی، کامنت، بلاک کامنت‌گذار، **بازنشر (Repost)** | ✅ کامل — مدل + endpoint هر هفت نوع تعامل با `services.py`، همه به Notification وصل. تایید دستی end-to-end در مرورگر با ۳ نوع اکانت (فاز حرفه‌ای). |
| `explore` | کشف، فید شخصی‌سازی‌شده، Trending، پیشنهاد Creator، **جستجوی full-text** | ✅ کامل — `explore/services.py` جدید: `SearchVector`/`SearchRank` روی PostgreSQL (وزن‌دار title/description)، فالبک `icontains` روی SQLite (dev/test) — `api_search` این سرویس رو صدا می‌زنه، دیگه منطق inline نیست |
| `moderation` | گزارش، AuditLog، صف بررسی ترک، اکشن staff | ✅ کامل شد (فاز حرفه‌ای) — approve/reject ترک، گزارش کامنت + مخفی‌سازی خودکار، تعلیق/رفع‌تعلیق. `AuditLog.TargetType.PAYOUT` برای اکشن‌های payout. صف‌های `track_queue`/`report_queue` حالا pagination (۳۰ در هر صفحه) + فیلتر وضعیت روی گزارش‌ها دارن (قبلاً فقط `[:200]` بدون فیلتر/صفحه‌بندی بودن). |
| `billing` | پلن، فاکتور، تراکنش، درخواست تسویه، **درگاه پرداخت واقعی** | ✅ کامل شد — `billing/services.py`: provider abstraction برای پرداخت (Zarinpal واقعی / Dev برای dev)، `start_payment`/`payment_callback`، `approve_payout`/`reject_payout` (کسر امتیاز واقعی از طریق PointLedger). صف `staff_payout_queue` حالا pagination + بخش «تاریخچه‌ی اخیر» (تصمیم‌های قبلی approve/reject) داره که قبلاً کاملاً غایب بود (فاز حرفه‌ای). |
| ~~`subscriptions`~~ | ~~پلن و اشتراک (نسخه قدیمی‌تر)~~ | ✅ حذف‌شده — در `_deprecated/` آرشیو شده، هیچ referenceای در کد زنده وجود ندارد |
| `core` | تنظیمات پلتفرم (Singleton)، **health check، backup، thumbnail pipeline، staff dashboard گرافیکی** | ✅ کامل شد (فاز حرفه‌ای) — `core/views.py::health_check`، `backup_db.py`، `core/templatetags/thumbnails.py` (حالا در `track_list`/`trending`/`library`/`playlist_detail`/پروفایل هم استفاده می‌شه، نه فقط discover). **`platform_dashboard` حالا گرافیکیه:** `static/vendor/chart.umd.min.js` (Chart.js، وندور محلی بدون CDN) + ۴ نمودار روند ۳۰روزه (پخش/درآمد/اقتصاد امتیاز/ثبت‌نام) و یک نمودار عملکرد ترک در `creator_detail`. `users_console`/`creators_console` هم حالا pagination دارن (قبلاً بدون صفحه‌بندی، همه‌ی نتایج یک‌جا). |
| `notifications` | Notification / Activity Feed | ✅ کامل — ۸ verb، grouping ۲۴ساعته، signal-driven، API + HTML، ۴۲ تست. فن‌اوت `notify_new_track_to_followers` از طریق Celery اجرا می‌شود. |
| `playlists` | پلی‌لیست شخصی، آیتم‌ها | ✅ کامل شد (فاز حرفه‌ای) — Rename (`api_playlist_rename`) و reorder دستی با ▲▼ (`api_playlist_reorder`، فیلد جدید `PlaylistItem.order`). **باگ واقعی رفع‌شده:** `playlist_detail` قبلاً فقط برای owner کار می‌کرد؛ حالا پلی‌لیست عمومی (`is_private=False`) برای همه قابل‌مشاهده است (دقیقاً الگوی دسترسی `track_detail`). |

**زیرساخت (بدون اپ Django مجزا):** Object Storage (django-storages، S3-compatible generic — Arvan/Liara/MinIO/AWS، فقط با `USE_S3_STORAGE=1` در prod فعال می‌شه)، Celery+Redis (broker مشترک با cache)، Sentry (اختیاری، فقط با `SENTRY_DSN`)۔ همه در `config/settings/prod.py`.

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
فاز نهایی (Production + مونتیزیشن + تجربه رقابتی) — ✅ بسته شد (۲۰۲۶-۰۸-۲۰): موارد #۱۵ تا #۲۰ رفع
                    شدند. Object Storage (S3-compatible)، Celery، Sentry، health check، backup، OTP SMS
                    واقعی (Kavenegar)، درگاه پرداخت واقعی (Zarinpal)، تسویه Creator با کسر امتیاز واقعی،
                    جستجوی full-text (Postgres)، OG/meta tags، thumbnail pipeline، داشبورد درآمد Creator،
                    داشبورد پلتفرم برای staff، waveform تزئینی، و بازبینی UX آپلود/انتظار بررسی.
                    جزئیات کامل: `.casset/execution/90-day-roadmap.md` بخش ۱۰
فاز حرفه‌ای (v1 professional — بازبینی جامع پلیر/پروفایل/آپلود/ادمین) — ✅ بسته شد (۲۰۲۶-۰۸-۲۰):
                    موارد #۲۹ تا #۳۴ رفع شدند. پلیر: volume/mute، اسکرابر native همیشه‌نمایان (لمس+کیبورد)،
                    skip ±۱۰s، shortcutهای کامل، reorder صف، نمای Now Playing تمام‌صفحه. امنیت پخش:
                    X-Forwarded-For پشت پراکسی قابل‌اعتماد (env-gated)، PlayEvent uniqueness شامل user.
                    پروفایل: باگ‌های لایک/صف مرده رفع شدند، دکمه اشتراک‌گذاری، لینک‌های اجتماعی، تب
                    ترک/پادکست/آلبوم/شو/پلی‌لیست، مودال فالوور/فالووینگ، خودسرویس Unpublish. پلی‌لیست:
                    Rename + reorder دستی، رفع باگ دسترسی عمومی. آپلود: drag&drop، progress واقعی XHR،
                    اعتبارسنجی کلاینت، تشخیص خودکار مدت‌زمان، پیش‌نمایش کاور. ادمین: Chart.js وندور محلی
                    + ۴ نمودار روند در platform_dashboard + نمودار عملکرد در creator_detail، pagination
                    روی همه‌ی صف‌های staff، تاریخچه‌ی payout. تصویر: thumbnail pipeline در ۵ تمپلیت جدید
                    + قرارداد یکسان `data-cover` (رفع باگ نمایش خراب کاور از discover). ۵۰۲ تست (از ۴۱۳)،
                    تایید کامل روی PostgreSQL واقعی، ruff تمیز. QA کامل با ۳ اکانت واقعی (شنونده/Creator/VIP)
                    در مرورگر. جزئیات کامل: `.casset/state/changelog.md`.
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

**تست روی PostgreSQL واقعی (مهم — نه اختیاری):**
دستورهای بالا روی SQLite اجرا می‌شن، ولی production روی Postgres است و این تفاوت تا الان **دو باگ واقعی** رو لو داده (موارد #۱۳/#۱۶ — `SUM(boolean)`). یک Postgres واقعی و محلی بدون نیاز به Docker یا دسترسی ادمین:
```powershell
python scripts/local_postgres.py start   # بالا آوردن سرور (idempotent) + چاپ متغیرهای اتصال
python scripts/local_postgres.py test    # کل تست‌سوییت روی همون Postgres واقعی
python scripts/local_postgres.py stop
```
دیتای این سرور در `.pgdata/` است (gitignore شده؛ پاک‌کردنش یعنی ریست کامل). پکیج `pgserver` در `[dev]` نصب می‌شه. توجه: یک تست (جستجوی full-text) روی SQLite **skip** می‌شه و فقط در این مسیر واقعاً اجرا می‌شه — پس عدد تست Postgres یکی بیشتر از SQLite است.

**داده‌ی نمونه برای تست دستی/مرورگر:**
```powershell
python manage.py seed_demo --users 33 --flush-demo
```
۳۳ کاربر (≈۹ Creator تاییدشده)، ترک، پخش، امتیاز از طریق `PointLedger`، فالو/لایک/کامنت، گزارش، و درخواست تسویه می‌سازه — یعنی همه‌ی داشبوردها و صف‌ها با داده‌ی واقعی قابل بررسی‌ان، نه حالت خالی. ورود: `demo_1` … `demo_33` با رمز `demo12345`.

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

نکته تنظیمات: `manage.py` و `pyproject.toml` هر دو پیش‌فرض `DJANGO_SETTINGS_MODULE=config.settings.dev` دارند. برای prod باید `config.settings.prod` صراحتاً ست بشه و `DJANGO_SECRET_KEY`, `PLAY_IP_SALT`, `PLAY_UA_SALT`, `KAVENEGAR_API_KEY` (SMS)، `ZARINPAL_MERCHANT_ID` (پرداخت) واقعی وجود داشته باشن — وگرنه استارت‌آپ با `ImproperlyConfigured` فیل می‌کنه (عمدی، fail-fast). سوییچ دیتابیس با `DB_ENGINE=sqlite|postgresql` در `.env`. Object Storage اختیاریه: `USE_S3_STORAGE=1` + چهار متغیر `S3_*` (هر backend S3-compatible: Arvan/Liara/MinIO/AWS).

Celery worker (برای فن‌اوت اعلان دنبال‌کننده‌ها؛ در dev/test بدون این هم کار می‌کنه چون eager است):
```powershell
celery -A config worker --loglevel=info
```

Backup دیتابیس (فقط Postgres):
```powershell
python manage.py backup_db --output-dir /path/to/backups
```
راهنمای کامل: `.casset/ops/backup.md`.

---

## ۸. معماری کد (Architecture Map)

- **Modular monolith با یک اپ Django به‌ازای هر دامنه.** لیست واقعی و فعال اپ‌ها همیشه از `config/settings/base.py::INSTALLED_APPS` بخون، نه از مستندات — این فایل منبع حقیقت است: `accounts`, `tracks`, `uploads`, `plays`, `interactions`, `playlists`, `explore`, `moderation`, `billing`, `notifications`, `core`.
- **Settings سه‌لایه:** `config/settings/base.py` (مشترک) ← `dev.py` / `prod.py` این را extend می‌کنن. فایل تخت قدیمی `config/settings.py` دیگر روی دیسک وجود ندارد — کاملاً حذف شده (commit `ea1d08b`، تایید مجدد توسط یک اجرای خودکار در ۲۰۲۶-۰۸-۲۰)، نه صرفاً بلاک‌شده با `raise ImportError` (که توصیف قدیمی این خط بود). هیچ import فعالی به `config.settings` (بدون `.dev`/`.prod`) در کدبیس وجود ندارد.
- **Routing تخت:** هر اپ `urls.py` خودش را دارد و در `config/urls.py` بدون prefix با `include()` مونت می‌شود. الگوی `<slug:handle>/` (پروفایل عمومی) عمداً آخرین pattern است — هر URL جدید باید **قبل از آن** در `config/urls.py` یا در `urls.py` یکی از اپ‌ها اضافه بشه، وگرنه این الگو مسیر جدید رو قورت می‌ده. `staff/` پیشوند مشترک صفحات داخلی staff است: `core.staff_urls` (`platform_dashboard`, `users_console`, `creators_console`, `creator_detail`) و `billing.staff_urls` (`payout_queue` و اکشن‌هاش) هر دو زیر همین پیشوند مونت شدن. **هشدار تاریخی:** `core.staff_urls` از قبل روی دیسک بود ولی تا ۲۰۲۶-۰۸-۲۰ هیچ‌وقت `include()` نشده بود — قبل از اضافه‌کردن یک `urls.py` جدید به هر اپی، حتماً چک کن که واقعاً در `config/urls.py` مونت شده، نه فقط اینکه فایل وجود داره.
- **Celery:** `config/celery.py` (app instance) + `config/__init__.py` آن را import می‌کند. `CELERY_TASK_ALWAYS_EAGER` در `config/settings/base.py` به‌طور خودکار بر اساس وجود `REDIS_URL` تنظیم می‌شود (بدون Redis = eager/سینک، برای dev/test بدون نیاز به worker). Task جدید برای اپی بساز در `<app>/tasks.py` با دکوریتور `@shared_task`، مثل `notifications/tasks.py`.
- **لایه Service/Domain** طبق قانون بخش ۲ باید منطق کسب‌وکار رو از `views.py` جدا نگه داره؛ فعلاً فقط `plays/services.py` و `notifications/services.py` این الگو را کامل پیاده کرده‌اند (نمونه‌ی مرجع برای سرویس جدید). بقیه‌ی اپ‌ها (`accounts`, `tracks`, `billing`, ...) هنوز بخشی از منطق را مستقیم در `views.py` دارند — وقتی منطق غیرپیش‌پاافتاده به یکی از این اپ‌ها اضافه می‌کنی، آن را در یک ماژول `services.py` مشابه بنویس، نه مستقیم در view.
- **گراف اصلی کسب‌وکار:** User → Creator (`accounts`) → Track/Album (`tracks`) → PlaybackSession/Event → QualifiedPlay (`plays`) → `PointLedger` (`plays/models.py`, نوشتن فقط از طریق `plays/services.py`) → Notification (`notifications`, signal-driven از `notifications/signals.py`) → Dashboard/Analytics.
- **بدون فرانت‌اند بیلد جدا.** `static/app.js` + `static/app.css` دستی نوشته شدن (بدون bundler/`package.json`)؛ رندر سمت سرور با Django templates در `templates/`.
- **`_deprecated/`** شامل `subscriptions` و `templates_subscriptions` آرشیوشده است — هرگز به آن‌ها ارجاع نده یا به `INSTALLED_APPS` برنگردون؛ `billing` تنها منبع حقیقت پلن/اشتراک است.
- فایل‌های `db.sqlite3.backup*` در ریشه‌ی ریپو snapshotهای دستی محلی‌اند، نه بخشی از schema رسمی یا migration — نادیده بگیر مگر کاربر صراحتاً بهشون اشاره کنه.
