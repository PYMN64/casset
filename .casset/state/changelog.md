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

## [2026-08-20] فاز حرفه‌ای — پلیر/پروفایل/آپلود/ادمین بازبینی جامع — ✅ بسته شد

**نوع:** Feature + Bugfix + Security + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه، درخواست صریح بازبینی جامع کل سایت به سطح حرفه‌ای، اجرای پیوسته تا پایان، commit فقط یک‌بار در پایان)

**تصمیم:** صاحب پروژه یک بازبینی end-to-end با تست مرورگری با ۳ نوع اکانت (شنونده عادی، Creator، VIP)
خواست، با تمرکز روی پلیر حرفه‌ای، پروفایل کاربری مرتب، مدیریت محتوای خودسرویس، آپلود روان، داشبورد
ادمین گرافیکی، و رفع هر دکمه/امکان نمادین. یک تصمیم صریح از کاربر گرفته شد (`AskUserQuestion`): لاگین
اجباری برای پخش **اضافه نشد** چون Embed و RSS پادکست ذاتاً باید بدون لاگین کار کنن؛ به‌جاش فقط
سخت‌سازی‌های امنیتی غیرمخرب (X-Forwarded-For پشت پراکسی قابل‌اعتماد، PlayEvent dedup شامل user) انجام شد.

پیش از کدنویسی، سه Explore agent موازی (پلیر/امنیت پخش، پروفایل/تعامل اجتماعی، آپلود/داشبورد ادمین)
کل کدبیس مرتبط رو خوندن؛ یافته‌هاشون پایه‌ی موارد #۲۹ تا #۳۴ بخش ۳ شد.

### فاز A — پلیر حرفه‌ای
`static/app.js`, `static/app.css`, `templates/base.html`. پلیر قبلاً جلوتر از تصور اولیه بود
(shuffle/repeat/speed/sleep-timer/resume/waveform-seek/queue-panel/playlist-modal/embed-modal همه از
قبل کار می‌کردن) — چیزی که واقعاً غایب بود اضافه شد: کنترل صدا (volume slider + mute، popover)، اسکرابر
زمانی native (`<input type=range>`، به‌جای فقط waveform click-only — لمس/کیبورد رایگان می‌گیره)، skip
±۱۰ ثانیه، shortcutهای صفحه‌کلید کامل (space/arrows/m/n/p با guard روی input focus)، reorder صف با
دکمه‌های ▲▼ (`moveQueueItem`)، و یک نمای «Now Playing» تمام‌صفحه جدید (`#npView`) با کاور بزرگ —
بازطراحی بصری با گرادیان/glassmorphism ملایم. **یافته حین کار:** موبایل (که waveform روش مخفیه) قبلاً
اصلاً هیچ راهی برای seek کردن نداشت — اسکرابر native این رو حل کرد چون همیشه‌نمایانه.

**باگ واقعی کشف‌شده (مورد #۲۹):** نیمی از تمپلیت‌ها `data-cover` رو HTML خام می‌ساختن، نیمی دیگه
(`discover.html`) فقط URL — `app.js` این مقدار رو `innerHTML` می‌کرد، یعنی پخش از discover کاور
پلیربار رو به‌صورت متن خام URL نشون می‌داد. قرارداد یکسان شد (فقط URL خام) در ۷ تمپلیت +
`explore/views.py::api_station`؛ `openPlayerBar` حالا `style.backgroundImage` استفاده می‌کنه، نه
`innerHTML` (امن‌تر هم هست).

### فاز B — سخت‌سازی امنیت پخش
`plays/utils.py`, `plays/models.py`, `plays/services.py`, `config/settings/base.py`. طبق تصمیم کاربر
(بدون login-gate): `TRUST_PROXY_HEADERS` (env، پیش‌فرض خاموش) برای فعال‌سازی امن `X-Forwarded-For` فقط
پشت یک پراکسی قابل‌اعتماد. **مورد #۳۲:** `PlayEvent` uniqueness از `(track, ip_hash, day_key)` به
`(track, user, ip_hash, day_key)` تغییر کرد (migration `plays/0003`) — قبلاً دو کاربر متفاوت پشت یک
IP/NAT در یک روز فقط یک PlayEvent می‌گرفتن (دومی silently drop). `services.py` گیت اول رو با
`user=listener_user` هم فیلتر می‌کنه تا با uniqueness جدید هماهنگ بمونه. ۵ تست رگرسیون جدید.

### فاز C — پروفایل حرفه‌ای
`templates/accounts/public_profile_pro.html` (بازنویسی کامل)، `accounts/views.py`, `accounts/urls.py`,
`static/app.js`, `static/app.css`, `playlists/`. **موارد #۳۰/#۳۱ رفع شدند:** دکمه‌ی ♥ حالا `data-track`
داره (قبلاً silent no-op)؛ دکمه‌ی ＋صف حالا src/title/by/cover کامل داره + `handleAddToQueue()` جدید در
app.js (قبلاً هیچ‌جا handler نداشت). اضافه شد: دکمه‌ی اشتراک‌گذاری (الگوی موجود `data-share`)، نمایش
لینک‌های اجتماعی با آیکون، تب‌بندی واقعی (ترک/پادکست/آلبوم/شو/پلی‌لیست — فقط تب‌هایی که واقعاً محتوا
دارن، طبق درس نسخه‌ی قبلی حذف‌شده با ۵ تب مرده)، مودال فالوور/فالووینگ (`api_user_connections` جدید در
accounts)، خودسرویس Unpublish/Publish (`uploads/views.py::toggle_track_visibility` — از
`Visibility.PRIVATE` موجود استفاده می‌کنه، بدون فیلد/migration جدید). `<style>` inline template به
`app.css` منتقل شد. Playlist rename (`api_playlist_rename`) + reorder دستی ▲▼
(`api_playlist_reorder`، فیلد جدید `PlaylistItem.order`، migration `playlists/0002`). **باگ واقعی
کشف‌شده (مورد #۳۱):** `playlist_detail` فقط owner-only بود با `@login_required` — پلی‌لیست عمومی
(`is_private=False`) که تازه از تب پروفایل بهش لینک دادم، برای کسی جز صاحبش 404 می‌داد؛ رفع شد با
همون الگوی دسترسی `track_detail`/`show_detail`.

### فاز D — آپلود حرفه‌ای
`static/upload.js` (جدید)، `templates/uploads/upload.html`, `static/app.css`. Drag & drop روی input
واقعی (نه یک مسیر موازی)، اعتبارسنجی کلاینت (پسوند/حجم) پیش از ارسال، تشخیص خودکار مدت‌زمان صوت در
مرورگر (`HTMLAudioElement.duration` روی فایل انتخاب‌شده)، پیش‌نمایش کاور (`FileReader`)، و progress bar
واقعی با `XMLHttpRequest.upload.onprogress` (fetch این event رو نداره) — قبلاً فقط دکمه غیرفعال می‌شد
بدون درصد واقعی. اعتبارسنجی سرور (`clean_audio`/`clean_cover`/`clean_video`) دست‌نخورده و مرجع نهایی
باقی موند — کلاینت فقط UX رو بهتر می‌کنه.

### فاز E — داشبورد ادمین گرافیکی
`static/vendor/chart.umd.min.js` (جدید — Chart.js v4.5.1 وندور محلی، بدون CDN، هماهنگ با معماری
بدون bundler پروژه)، `core/staff_views.py`, `templates/staff/platform_dashboard.html`,
`templates/staff/creator_detail.html` (بازطراحی کامل — قبلاً رنگ‌های hardcoded روشن `#eee`/`#fafafa`
داشت که با تم تیره‌ی سایت کاملاً ناهماهنگ بود)، `billing/staff_views.py`, `moderation/views.py`.
۴ نمودار روند ۳۰روزه در platform_dashboard (پخش واجد شرایط روزانه از `PlayEvent`، درآمد روزانه از
`Invoice`، اقتصاد امتیاز روزانه از `PointLedger`، ثبت‌نام کاربر جدید) + نمودار عملکرد ترک در
creator_detail. Pagination (۳۰ در صفحه، Django Paginator) به `users_console`, `creators_console`,
`report_queue` (+ فیلتر وضعیت), `track_queue`, `staff_payout_queue` اضافه شد — قبلاً همه یا `[:200]`
بدون صفحه‌بندی بودن یا اصلاً محدودیتی نداشتن. `staff_payout_queue` یک بخش «تاریخچه‌ی اخیر» جدید داره
(۲۰ تصمیم آخر approve/reject) که قبلاً کاملاً غایب بود — تصمیم‌های قبلی staff هیچ‌جا قابل‌مشاهده نبودن.
**مورد #۳۴:** `t.publish_at` (فیلد نامعتبر) در creator_detail به `published_at` واقعی اصلاح شد.

### فاز F — پرداخت به جزئیات بصری
`core/templatetags/thumbnails.py` (بدون تغییر، فقط استفاده‌ی گسترده‌تر)، ۵ تمپلیت
(`track_list`, `trending`, `library`, `playlist_detail`, `public_profile_pro`) که قبلاً هیچ کاور
واقعی نشون نمی‌دادن (یا یک دات رنگی ساده، یا هیچ). کلاس مشترک جدید `.row-cover` در `app.css` — کاور
واقعی (thumbnail 120×120) وقتی موجوده، یک gradient placeholder ملایم (نه جای خالی خام) وقتی نیست.

### فاز G — QA کامل با ۳ نوع اکانت واقعی در مرورگر
با `seed_demo`: `demo_4` (شنونده عادی، غیر-VIP، غیر-Creator)، `demo_1` (Creator تاییدشده)، `demo_2`
(VIP، موقتاً از طریق shell اعطا شد برای این تست). روی `track_detail` همه‌ی دکمه‌ها end-to-end تست شدن:
like/favorite/repost (شمارنده‌ها درست افزایش پیدا کردن)، کامنت add/like/delete، اشتراک‌گذاری، embed
modal (کد iframe درست)، playlist-add modal، station (صف رادیویی ساخته شد). دانلود VIP برای `demo_2`
تایید شد (`200 audio/mpeg` با attachment filename درست)؛ برای `demo_4` غایب بود (درست). Creator Studio
برای `demo_1` با داده‌ی واقعی (موجودی امتیاز، ledger، سوابق payout، آمار ۳۰روزه) بدون خطا رندر شد.
جستجوی full-text تایید شد. هیچ دکمه‌ی مرده‌ی جدیدی در این پاس پیدا نشد (همه‌ی موارد شناخته‌شده در
فازهای A-F رفع شده بودن).

### فاز H — تست کامل + تایید Postgres + مستندسازی
`ruff check .` (۱۱ خطای E402/F841 ناشی از این پاس پیدا و رفع شد — imports جابه‌جا نشده بعد از insert،
یک متغیر استفاده‌نشده در تست)، `manage.py test` → **۵۰۲ تست سبز روی SQLite** (از ۴۱۳ قبل از فاز، شامل
تست `soundfile` که قبلاً نصب نبود در این محیط و نصب شد)، `manage.py makemigrations --check` تمیز،
`manage.py check --deploy` زیر `config.settings.prod` تمیز (فقط W004/W008/W009 مورد‌انتظار با env
placeholder). **تایید کامل زنده روی PostgreSQL واقعی** (`scripts/local_postgres.py test`، همون الگوی
فازهای قبلی): **۵۰۳ تست، همه pass** — بدون هیچ باگ کلاس `Sum(boolean)` جدید (دو migration جدید این
پاس — `plays/0003`, `playlists/0002` — روی Postgres واقعی بدون خطا اعمال و تست شدن).

**فایل‌های عمده تغییرکرده/جدید:** `static/app.js` (بازنویسی گسترده)، `static/app.css` (+۳۰۰ خط)،
`static/upload.js` (جدید)، `static/vendor/chart.umd.min.js` (جدید، وندور)، `templates/base.html`
(playerbar بازساخت کامل + Now Playing view)، `templates/accounts/public_profile_pro.html` (بازنویسی
کامل)، `templates/staff/creator_detail.html` (بازنویسی کامل، تم تیره)، `templates/uploads/upload.html`،
`accounts/views.py`/`urls.py`، `uploads/views.py`/`urls.py`، `playlists/models.py`/`views.py`/`urls.py`
(+ migration)، `plays/utils.py`/`models.py`/`services.py` (+ migration)، `core/staff_views.py`،
`billing/staff_views.py`، `moderation/views.py`، `explore/views.py`، `config/settings/base.py`.

**تایید:**
- `python manage.py test` → **۵۰۲ تست** روی SQLite، همه pass
- **تایید زنده روی PostgreSQL واقعی** (`scripts/local_postgres.py test`): **۵۰۳ تست**، همه pass
- `ruff check .`, `manage.py makemigrations --check`, `manage.py check --deploy` — همه تمیز
- تایید دستی کامل در مرورگر با ۳ اکانت واقعی متفاوت (شنونده/Creator/VIP): پلیر (volume/seek/skip/
  keyboard/queue-reorder/Now-Playing — همه با آزمایش JS مستقیم روی DOM تایید شدن، نه فقط بازرسی کد)،
  پروفایل (تب‌ها، لایک/صف رفع‌شده، مودال فالوور، اشتراک‌گذاری)، آپلود (drag&drop، اعتبارسنجی کلاینت،
  پیش‌نمایش کاور، آپلود end-to-end با ردیابی XHR واقعی تا redirect نهایی)، پلی‌لیست (rename + reorder با
  reload واقعی صفحه)، داشبورد ادمین (۴ چارت + چارت creator_detail، pagination) — و دانلود VIP-gated.

**وضعیت CLAUDE.md:** موارد #۲۹ تا #۳۴ بسته شدند ✅. جدول دامنه‌ها (بخش ۴) برای `tracks`, `uploads`,
`plays`, `moderation`, `billing`, `core`, `playlists` به‌روز شد. بخش ۶: فاز حرفه‌ای ✅ بسته شد.

**Commit و تگ:** `f396b3c` — به `origin/master` push شد. تگ annotated `v1.2.0` روی همین commit ساخته و
push شد (`git ls-remote --tags origin` قابل تایید است). این تگ از این پس **نسخه‌ی مبنا (baseline)** برای
تمام کارهای بعدی روی این ریپازیتوریه — طبق درخواست صریح صاحب پروژه. سه تگ سبک‌وزن قدیمی محلی
(`v.2.0.0`, `v1.1.0`, `v1.1.0-stabilization`, `v2`, `v2-safe`) از جلسات قبلی روی دیسک پیدا شدن که هیچ‌وقت
push نشده بودن و به این خط تاریخچه مربوط نیستن — دست‌نخورده باقی موندن (تصمیم حذف/تمیزکاری‌شون با کاربره)،
فقط در نام‌گذاری این تگ جدید نادیده گرفته شدن.

---

## [2026-08-20] فاز نهایی — Production، مونتیزیشن واقعی، تجربه رقابتی — ✅ بسته شد

**نوع:** Architecture + Feature + Security + Bugfix + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه، اجرای پیوسته بدون توقف طبق درخواست صریح)

**تصمیم:** آخرین فاز قبل از رقابت واقعی با شنوتو/کست‌باکس/طاقچه. سه دسته: (A) سخت‌سازی Production،
(B) مونتیزیشن واقعی، (C) تجربه رقابتی — به‌علاوه یک آیتم ۰ (SMS واقعی) و دو داشبورد اضافه‌شده حین کار
طبق درخواست کاربر (داشبورد درآمد/امتیاز شفاف Creator + داشبورد آماری پلتفرم برای staff).

قبل از هر کدی، طبق قانون بخش ۵ CLAUDE.md، `git status`/`git log` چک شد (working tree تمیز، منطبق با
مستندات) — برخلاف چند فاز قبل، این‌بار هیچ کار موازی کامیت‌نشده‌ای پیدا نشد.

### ۰. OTP SMS واقعی (Kavenegar)
`accounts/services.py` (جدید) — provider abstraction دقیقاً مثل الگوی Zarinpal پایین: `ConsoleSmsProvider`
(dev/test، فقط log می‌کنه) و `KavenegarSmsProvider` (API واقعی `sms/send.json`). انتخاب با `SMS_PROVIDER`
env. **یافته حین بررسی:** `phone_start_view` تا امروز در production عملاً هیچ SMS واقعی ارسال نمی‌کرد —
فقط پیام "کد ارسال شد" نشون می‌داد بدون اینکه واقعاً چیزی بفرسته (مورد #۲۰ بخش ۳). `config/settings/prod.py`
حالا بدون `SMS_PROVIDER=kavenegar` + `KAVENEGAR_API_KEY` واقعی اصلاً بالا نمی‌آد.

### دسته A — سخت‌سازی Production
- **Object Storage:** `django-storages[s3]` + `boto3` اضافه شد. `config/settings/prod.py`:
  `USE_S3_STORAGE=1` فعال می‌کنه (S3-compatible عمومی — Arvan/Liara/MinIO/AWS، فقط با env عوض می‌شه، قفل
  روی یک provider نیست)؛ بدون این env، رفتار prod مثل قبل (fail-fast اگه کلیدها ناقص باشن). **باگ واقعی
  رفع‌شده حین این کار:** `Track.cover` و `UserProfile.cover` هر دو `upload_to="covers/"` بودن — collision
  واقعی روی object storage. Namespace شدن (`tracks/covers/`, `accounts/covers/`, ...) + migration.
  **یافته امنیتی جانبی:** `accounts/forms.py::ProfileSettingsForm` هیچ `clean_cover`/`clean_avatar` نداشت
  (مورد #۱۸) — با `core/validators.py::validate_image` مشترک رفع شد.
- **Celery + Redis:** `config/celery.py` + wiring در `config/__init__.py`. `notifications/tasks.py::
  notify_new_track_to_followers_task` جایگزین فراخوانی سینک قبلی در `notifications/signals.py` شد.
  `CELERY_TASK_ALWAYS_EAGER` خودکار بر اساس وجود `REDIS_URL` (بدون Redis = eager، برای dev/test بدون نیاز
  به worker).
- **Sentry:** `sentry-sdk[django]`، فقط با `SENTRY_DSN` در prod init می‌شه.
- **Health check:** `core/views.py::health_check` (`GET /healthz/`) — چک DB + cache واقعی، نه فقط 200 ثابت.
- **Backup:** `core/management/commands/backup_db.py` (`pg_dump` wrapper، فقط روی Postgres) +
  `.casset/ops/backup.md` (مستندسازی cron).
- **باگ واقعی کشف‌شده (مورد #۱۵):** `core/staff_urls.py` (users/creators console + creator_detail) از قبل
  روی دیسک بود ولی **هیچ‌وقت در `config/urls.py` mount نشده بود** — کل پنل staff غیرقابل‌دسترس بود، صفر
  تست هم داشت. مونت شد در `staff/` + ۱۵+ تست جدید (`core/tests.py`).

### دسته B — مونتیزیشن واقعی
- **درگاه پرداخت زرین‌پال:** `billing/services.py` (جدید) — provider abstraction: `ZarinpalProvider`
  (API واقعی v4: request/verify) و `DevPaymentProvider` (فقط DEBUG، منطق قدیمی `activate_vip_dev` رو در
  قالب همون Invoice/Transaction واقعی حفظ می‌کنه). `start_payment`/`payment_callback` views جدید.
  `config/settings/prod.py` بدون `PAYMENT_PROVIDER=zarinpal` + `ZARINPAL_MERCHANT_ID` واقعی fail می‌کنه.
  منبع حقیقت عوض نشد — همون `Invoice`/`Plan`/`Transaction` قبلی (که از قبل webhook-ready بودن).
- **Payout واقعی:** **باگ واقعی کشف‌شده (مورد #۱۷):** `create_payout_request` هیچ‌وقت امتیاز کاربر رو کم
  نمی‌کرد — یعنی بعد از تایید، همون امتیاز باز قابل درخواست مجدد بود. `PayoutRequest.points` (فیلد جدید،
  امتیاز رو در لحظه درخواست قفل می‌کنه) + `billing/services.py::approve_payout` که کسر رو از طریق
  `PointLedger` (delta منفی، reason=`PAYOUT_DEDUCTION` جدید در `plays/models.py`) انجام می‌ده — نه
  دستکاری مستقیم `UserProfile.points`. `billing/staff_views.py` صف تایید/رد payout، الگوی دقیق
  `moderation/report_queue.html`. `AuditLog.TargetType.PAYOUT` جدید در `moderation/models.py`.

### دسته C — تجربه رقابتی
- **جستجوی full-text:** `explore/services.py` (جدید) — `SearchVector`/`SearchRank` وزن‌دار (title=A,
  description=B) روی PostgreSQL، فالبک `icontains` روی SQLite (چون dev/test پیش‌فرض SQLite است) — بدون
  فیلد/migration جدید (annotate در لحظه کوئری). `explore/views.py::api_search` این سرویس رو صدا می‌زنه.
- **OG/Meta tags:** `{% block meta %}` در `base.html` (fallback عمومی) + override در `track_detail.html`
  و `public_profile_pro.html` (og:title/description/image از cover/avatar واقعی، twitter:card).
  **یافته جانبی (مورد #۱۹):** `templates/accounts/public_profile.html` یک قالب orphan بود — هیچ view‌ای
  رندرش نمی‌کرد؛ حذف شد (همون الگوی حذف `tracks/detail.html` در فاز ۳).
- **Thumbnail pipeline:** `core/templatetags/thumbnails.py::thumbnail_url` — بدون فیلد/migration جدید،
  lazy generate + cache روی هر storage backend (local یا S3)، fallback امن به تصویر اصلی در صورت خطا.
  در `discover.html` (سه گرید کاور) با `loading="lazy"` وایر شد.
- **Waveform:** تصمیم صریح — waveform واقعی (peaks از فایل صوتی) نیاز به ffmpeg/pydub (dependency سیستمی
  جدید) داره که هزینه‌اش برای یک آیتم "nice-to-have" توجیه نداشت. نسخه تزئینی CSS-animated (۱۶ بار،
  seed ثابت) در playerbar (`#pbWave` در `base.html`، انیمیشن با `hookWaveformAnimation` در `app.js`).
- **داشبورد درآمد/امتیاز Creator (درخواست صریح کاربر):** `creator_studio_view` حالا `recent_ledger`
  (۲۵ تراکنش اخیر PointLedger با دلیل دقیق) و `recent_payouts` رو هم به context اضافه می‌کنه؛
  `creator_studio.html` یک بخش «تراکنش‌های اخیر امتیاز» شفاف نشون می‌ده.
- **داشبورد آماری پلتفرم برای staff (درخواست صریح کاربر):** `core/staff_views.py::platform_dashboard`
  (mount شده در `staff/`، صفحه اول staff) — درآمد کل (Sum روی Invoiceهای PAID)، امتیاز صادرشده/بازخریدشده،
  صف‌های نیازمند بررسی (ترک/گزارش/payout/creator در انتظار) با لینک مستقیم.
- **بازبینی UX آپلود/انتظار بررسی:** `my_tracks.html` برچسب‌های وضعیت فارسی + بج رنگی (به‌جای مقدار خام
  DB مثل `submitted`)؛ `upload.html` دکمه ارسال حین آپلود غیرفعال می‌شه + پیام "در حال آپلود…" (فایل‌های
  صوتی/ویدیویی بزرگ دیگه بی‌بازخورد نمی‌مونن).

### باگ دوم Sum(boolean) — کشف‌شده توسط همون تایید زنده Postgres (مورد #۱۶)
دقیقاً طبق روال فازهای قبل، بعد از پایان کدنویسی، کل تست‌سوییت روی یک PostgreSQL واقعی (۱۶.۲، از طریق
پکیج `pgserver`، یکبار‌مصرف) اجرا شد — هم `migrate` زیر `dev`/`prod`، هم کل تست‌ها. این بار
`core/staff_views.py::users_console` رو لو داد: همون الگوی `Sum("...point_awarded")` روی یک `BooleanField`
(مورد #۱۳ قبلی، ولی این‌بار در یک view دیگه) — چون این view تا همین فاز اصلاً mount نشده بود (مورد #۱۵)،
هیچ‌وقت این مسیر لمس نشده بود. با `Count(..., filter=Q(...=True))` رفع شد؛ یک تست رگرسیون اضافه شد.
جانبی: `BackupDbCommandTests.test_refuses_on_sqlite` هم سخت‌تر شد (settings mock صریح) چون زیر Postgres
واقعی رفتارش نامعین می‌شد.

**فایل‌های عمده تغییرکرده/جدید:** `accounts/services.py`, `billing/services.py`,
`billing/staff_views.py`/`staff_urls.py`, `explore/services.py`, `core/views.py`, `core/urls.py`,
`core/templatetags/thumbnails.py`, `core/management/commands/backup_db.py`, `config/celery.py`,
`notifications/tasks.py`, migrations در `accounts`/`tracks`/`billing`/`moderation`/`plays`، + قالب‌های
`staff/platform_dashboard.html`, `billing/staff_payout_queue.html`, و ویرایش‌های گسترده در `base.html`,
`creator_studio.html`, `my_tracks.html`, `upload.html`, `vip.html`, `discover.html`, `track_detail.html`,
`public_profile_pro.html`.

**تایید:**
- `python manage.py test` → **۴۱۳ تست** (از ۳۵۱ قبل از فاز)، همه pass روی SQLite
- **تایید زنده کامل روی PostgreSQL واقعی (۱۶.۲، pgserver یکبارمصرف):** `migrate` زیر `dev` و `prod`، و کل
  ۴۱۳ تست — همه pass بعد از رفع باگ #۱۶. دقیقاً همون سطح تاییدی که فاز #۴ قبلی داشت.
- `makemigrations --check`, `ruff check .`, `manage.py check`, `manage.py check --deploy` (با env کامل
  prod شامل کلیدهای S3/Zarinpal/Kavenegar) — همه تمیز (فقط همون W004 قدیمی و بی‌خطر HSTS)
- تایید دستی کامل در مرورگر روی `runserver` واقعی: خرید VIP end-to-end (`start_payment` →
  `payment_callback` → `mark_paid` → `has_vip()=True`)، صف تایید payout برای staff، داشبورد آماری پلتفرم،
  داشبورد درآمد Creator، پنل کاربران staff (قبلاً غیرقابل‌دسترس)، بج‌های وضعیت فارسی در my_tracks،
  بازخورد "در حال آپلود" روی فرم آپلود، og:title/og:image واقعی روی track_detail، و ۱۶ بار waveform در
  playerbar با انیمیشن حین پخش.

**وضعیت CLAUDE.md:** موارد #۱۵ تا #۲۰ بسته شدند ✅. جدول دامنه‌ها (بخش ۴) برای همه اپ‌های لمس‌شده به‌روز
شد. بخش ۶: فاز نهایی ✅ بسته شد. بخش ۸ (Architecture Map): نکته staff routing + Celery اضافه شد.

**Commit نشد** — طبق دستور صریح کاربر، منتظر تایید نهایی برای commit.

---

## [2026-08-20] فاز دوم — پادکست (Show/RSS)، waveform واقعی، Repost، Station، Embed، نشان تایید

**نوع:** Feature + Bugfix + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**تصمیم:** کاربر خواست تمام پیشنهادهای «فاز دوم» (مقایسه با ساندکلاد/کست‌باکس در یک artifact جداگانه) به‌صورت کامل پیاده‌سازی بشه — هم امکانات باطنی هم ظاهری — و در پایان فول تست بشه، بدون نیاز به تایید قبل از commit.

### دسته MUST — زیرساخت‌های واقعاً وجودی

**۱. پادکست: Show + RSS (بدون مدل جدید)** — `tracks.Album` که از قبل `content_type=podcast` داشت، به‌عنوان «Show» بازاستفاده شد (طبق قانون «بازنویسی ممنوع»، نه مدل جدید). `tracks/feeds.py::ShowRSSFeed` با `django.contrib.syndication` + یک `ITunesFeedGenerator` سفارشی (namespace `itunes:`) — این تنها راهیه که یک پادکست منتشرشده در کاست بتونه توی اپل پادکست/گوگل پادکست هم دیده بشه. `tracks/views.py::show_detail` صفحه‌ی عمومی هر Show با لیست قسمت‌ها + لینک RSS. مسیرها در `tracks/urls.py`: `show/<id>/` و `show/<id>/rss.xml`.

**۲. Waveform واقعی (نه تزئینی)** — تصمیم قبلی («نیاز به ffmpeg، توجیه نداره») این بار عوض شد: پکیج `soundfile` (بایندینگ Python برای `libsndfile` نسخه ≥۱.۱، MP3/WAV/FLAC/OGG رو مستقیم decode می‌کنه، **بدون نیاز به ffmpeg سیستمی** — تایید عملی شد قبل از هر کدنویسی). `tracks/audio_processing.py::extract_waveform_peaks` — peak-envelope با `numpy`، ۱۲۰ نمونه نرمال‌شده. `Track.waveform_peaks` (JSONField, migration جدید) پر می‌شه از طریق `tracks/tasks.py::generate_waveform_task` (Celery، حین آپلود/ویرایش). پلیربار (`#pbWave` در `base.html`) الان دو لایه bar-row داره (base خاموش + progress روشن، clip شده به درصد پخش) با کلیک-برای-seek؛ فالبک به همون انیمیشن تزئینی قبلی وقتی peak وجود نداره.

**۳. UI کامل پلی‌لیست + رفع کد مرده واقعی** — حین بررسی، مشخص شد `#plModal` (افزودن به پلی‌لیست) و `#qPanel` (صف پخش) **کاملاً در JS پیاده‌سازی شده بودن ولی هیچ‌جای HTML وجود نداشتن** — یعنی این دو دکمه در سایت واقعی هیچ کاری نمی‌کردن (item #۲۶ بخش ۳ CLAUDE.md). هر دو + یک `#embedModal` جدید به `base.html` اضافه شدن. همچنین ۲ باگ واقعی دیگه رفع شد: `library_view` بدون `annotate(item_count=...)` (همیشه «۰ ترک» نشون می‌داد) و `playlist_detail.html` که `{{ playlist.name }}` رو رندر می‌کرد در حالی که context key واقعی `pl` بود (نام پلی‌لیست هیچ‌وقت نشون داده نمی‌شد). `playlists/tests.py` از خالی به تست کامل رسید.

### دسته SHOULD

- **Repost** (`interactions.Repost`، جدا از Like/Favorite) — مدل + `toggle_repost` در services.py + endpoint + notification verb جدید `track_reposted` + دکمه در `track_detail.html`.
- **Station (رادیوی پیوسته)** — `explore/services.py::station_for_creator` + `api_station` endpoint؛ دکمه‌ی «📻 رادیوی این سازنده» یک صف پخش تصادفی از بقیه‌ی ترک‌های همون Creator می‌سازه و پخش خودکار شروع می‌کنه.
- **نشان تایید‌شده (Verified badge)** — `UserProfile.is_verified` + `moderation/services.py::set_verified` (idempotent، AuditLog می‌نویسه) + دکمه در `staff:creator_detail` + نمایش در پروفایل/صفحه‌ی ترک.
- **Embed widget** — `tracks/views.py::track_embed` (صفحه‌ی مینیمال، `@xframe_options_exempt` تا بشه توی iframe بیرونی جاسازی بشه) + مودال کپی کد در سایت.
- **ایمیل خلاصه‌ی هفتگی Creator** — `notifications/tasks.py::send_creator_weekly_digest`، زمان‌بندی‌شده با `CELERY_BEAT_SCHEDULE` (نیاز به پروسه‌ی جدا `celery -A config beat` در prod). فقط وقتی خبری هست ایمیل می‌ره (صفر پخش/فالوور = بی‌صدا) — ایمیل خالی، Creator رو عادت به نادیده‌گرفتن دایجست می‌ده. `EMAIL_*` جدید در `config/settings/base.py`، فالبک به console backend وقتی `EMAIL_HOST` خالیه (مثل Sentry، بدون fail-fast چون نیاز حیاتی نیست).

### ظاهر
Hero برای بازدیدکننده‌ی ناشناس در `/discover/` (پیشنهاد ارزش + CTA ثبت‌نام/انتشار)، بازنویسی کامل پروفایل به فارسی (فاز قبل)، و پاک‌سازی چند رشته‌ی انگلیسی باقی‌مونده (`search.html`, `renderSearchResults`, `renderQueuePanel`, مودال پلی‌لیست).

### باگ واقعی دیگه (کشف‌شده حین کار، نه فرض)
`tracks/views.py::track_detail` هیچ‌وقت `can_download` رو در context نمی‌ذاشت — یعنی دکمه‌ی دانلود VIP (که از فاز قبل با `download_track` view آماده بود) **هیچ‌وقت، برای هیچ کاربری** نشون داده نمی‌شد. رفع شد + تست رگرسیون.

### seed_demo تکمیل شد
تراک‌های seed هیچ فایل صوتی واقعی نداشتن (`track.audio` خالی) — یعنی کل ردیف اکشن (پخش/لایک/بازنشر/پلی‌لیست/اشتراک/embed) به‌خاطر `{% if track.audio %}` در تمپلیت مخفی می‌موند و قابل تست دستی نبود. یک تون سینوسی واقعی (WAV، قابل‌decode) به هر ترک seed اضافه شد + waveform واقعی‌اش هم از قبل محاسبه می‌شه.

**تایید:**
- `ruff check .` → **All checks passed**
- `python manage.py test` (SQLite) → **۴۷۶ تست، OK** (۱ skip = تست full-text مخصوص Postgres)
- `python scripts/local_postgres.py test` (PostgreSQL واقعی) → **۴۷۶ تست، OK، بدون skip**
- `makemigrations --check` / `manage.py check` → تمیز
- **تایید end-to-end کامل در مرورگر واقعی** با `seed_demo --users 33`: پخش با waveform واقعی (رندر لایه‌ی progress، کلیک-seek)، بازنشر (شمارنده ۰→۱ + Notification در DB تایید شد)، افزودن به پلی‌لیست از مودال (PlaylistItem واقعاً در DB ساخته شد)، صف پخش، مودال Embed (کد iframe درست + خود صفحه‌ی embed لود شد)، اعطای نشان تایید از پنل staff (بج واقعاً در پروفایل عمومی ظاهر شد).

**وضعیت CLAUDE.md:** موارد #۲۶ تا #۲۸ اضافه و بسته شدند. دامنه‌های `tracks`, `interactions`, `accounts` به‌روز شدند.

---

## [2026-08-20] تثبیت نسخه ۱ (MVP قابل بهره‌برداری) — Postgres دائمی، ۵ باگ جدید، پاک‌سازی کد مرده

**نوع:** Bugfix + Infrastructure + Architecture + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**نقطه شروع:** خطای واقعی کاربر در PyCharm: `ModuleNotFoundError: No module named 'celery'`. ریشه‌یابی نشون داد پکیج‌های جدید (celery/boto3/django-storages/sentry-sdk/requests) در پایتون سراسری نصب شده بودن نه در `.venv` پروژه که PyCharm ازش استفاده می‌کنه. با `./.venv/Scripts/python.exe -m pip install -e ".[dev]"` رفع شد. **درس:** روی این ماشین همیشه باید از `.venv/Scripts/python.exe` استفاده بشه، نه `python` سراسری.

**یافته مهم درباره‌ی وضعیت کد:** یک session موازی هم‌زمان روی همین ریپو کار کرده بود و دسته C (جستجوی full-text، thumbnail pipeline، داشبورد پلتفرم، OG tags، UX آپلود) رو ساخته بود. کد اون session و کد این session روی دیسک ادغام شدن. ممیزی کامل انجام شد و ادغام منسجم بود (health check این session + `platform_dashboard` اون session هر دو سالم، باگ `Sum(boolean)` در `users_console` هم رفع‌شده).

### PostgreSQL به‌عنوان زیرساخت دائمی (نه تست موقت)
درخواست صریح کاربر: «دیگه این موضوع پیش نیاد که Postgres هنوز فعال نشده». فاز قبل از `pgserver` به‌عنوان یک ابزار یک‌بارمصرف استفاده کرده بود؛ حالا تبدیل به زیرساخت دائمی شد:
- `scripts/local_postgres.py` (جدید) — `start`/`stop`/`test`/`migrate`/`check`. یک PostgreSQL کامل بدون نیاز به Docker یا دسترسی ادمین.
- `pgserver` به `[project.optional-dependencies] dev` اضافه شد.
- `.pgdata/` و `backups/` به `.gitignore` اضافه شدند.
- **رفع مشکل tzdata که فاز قبل هم خورده بود:** باینری pgserver در ویندوز بدون `share/postgresql/timezone` میاد و چون جنگو موقع هر اتصال `SET TIME ZONE 'UTC'` می‌زنه، هیچ اتصالی برقرار نمی‌شد. نکته‌ی ظریف: یک `share/timezone` (بدون `postgresql/`) از قبل پر بود ولی **هرگز خونده نمی‌شه** — sharedir واقعی این بیلد `share/postgresql` است. تابع تشخیص اول اشتباهاً به‌خاطر همون دایرکتوری بی‌مصرف زودهنگام return می‌کرد.
- **نتیجه: کل ۴۱۷ تست روی PostgreSQL واقعی pass شدن** (روی SQLite ۴۱۶ تست + ۱ skip؛ اون یکی تست جستجوی full-text مخصوص Postgres است که فقط در این مسیر واقعاً اجرا می‌شه).

### ۵ باگ واقعی جدید کشف و رفع‌شده (موارد #۲۱ تا #۲۵ جدول بخش ۳)
1. **بحرانی — اسلاگ فارسی:** `t/<slug:slug>/` از converter داخلی جنگو استفاده می‌کرد که فقط ASCII می‌پذیره، ولی `Track.save()` با `allow_unicode=True` اسلاگ فارسی می‌سازه. یعنی **صفحه‌ی هر ترک با عنوان فارسی کاملاً غیرقابل‌دسترس بود** — روی یک پلتفرم فارسی یعنی تقریباً تمام محتوای واقعی. با `core/converters.py::UnicodeSlugConverter` (رجیستر‌شده به‌عنوان `uslug`) رفع شد. **چرا هیچ‌وقت لو نرفته بود:** همه‌ی تست‌های قبلی عنوان انگلیسی داشتن. حین اضافه‌کردن لینک عنوان ترک در پروفایل، به‌صورت `NoReverseMatch` در مرورگر واقعی خودش رو نشون داد. ۴ تست رگرسیون فارسی اضافه شد.
2. **امنیتی — `config/settings/__init__.py`:** یک `from .dev import *` داشت، یعنی `DJANGO_SETTINGS_MODULE=config.settings` بی‌صدا تنظیمات dev رو لود می‌کرد (`DEBUG=True`، کوکی ناامن، SQLite، SECRET_KEY تصادفی) — روی production یک فاجعه‌ی کاملاً خاموش. حالا `ImportError` صریح می‌ده. **نکته‌ی پیاده‌سازی:** شرطی نوشته شد (`if os.environ.get(...) == "config.settings"`) چون پایتون قبل از زیرماژول پکیج والد رو import می‌کنه و یک `raise` بی‌قید مسیر سالم `config.settings.dev` رو هم می‌شکست.
3. **OG image با S3:** `{{ request.scheme }}://{{ request.get_host }}{{ ...url }}` با `USE_S3_STORAGE=1` (که `FileField.url` خودش مطلقه) URL خراب دوتایی می‌ساخت. `core/templatetags/casset_urls.py::abs_url` جایگزین شد.
4. **کامنت چندخطی `{# #}`:** در جنگو `{# #}` فقط تک‌خطیه؛ نسخه‌ی چندخطی به‌عنوان متن خام در صفحه رندر می‌شد (در مرورگر دیده شد، نه در تست). به `{% comment %}` تبدیل شد + یک اسکن روی کل `templates/` برای اطمینان از نبود مورد مشابه.
5. **`seed_demo` و کش کهنه:** `creator.profile.points` از یک آبجکت حافظه‌ای قدیمی خونده می‌شد (قبل از بازمحاسبه‌ی امتیاز)، پس هیچ payout ساخته نمی‌شد.

### پاک‌سازی کد مرده
- **۳ قالب یتیم حذف شد:** `accounts/creator_dashboard.html`, `playlists/index.html`, `tracks/artist_profile.html`. (نکته: `artist_profile` یک view داره ولی فقط `redirect` می‌کنه و هرگز قالبش رو render نمی‌کنه.)
- اسکن با resolver خود جنگو: **هر view روت شده** — هیچ view مرده‌ای نموند.
- اسکن توابع `services.py`: هیچ تابع بدون فراخوان.
- **`ruff check .` برای اولین بار در تاریخ پروژه کاملاً تمیز شد** (از ۹۱ مورد اولیه به صفر) — ۴ خطای `E402` قدیمی `config/urls.py` هم با جابه‌جایی `admin.site.*` به بعد از import رفع شد.

### پنل ادمین حرفه‌ای
۴ مدل ثبت‌نشده اضافه شدند؛ حالا **هر ۲۵ مدل پروژه در ادمین‌اند**:
- `moderation.AuditLog` — عمداً **فقط-خواندنی** (`has_add/change/delete_permission` هر سه `False`) چون قابل‌ویرایش بودنِ رد حسابرسی کل هدفش رو از بین می‌بره. نوشتنش منحصراً از لایه‌ی service است.
- `explore.FeaturedPin` — با `list_editable` روی `position`/`is_active`؛ تنها جاییه که staff می‌تونه بدون کد، محتوای صفحه‌ی کشف رو کنترل کنه.
- `playlists.Playlist` (+ inline آیتم‌ها، با `annotate` برای جلوگیری از N+1 در ستون تعداد) و `playlists.PlaylistItem`.

### داده‌ی نمونه واقعی
`core/management/commands/seed_demo.py` (جدید) — ۳۳ کاربر، ۳۲ ترک، ۵۶۴ پخش، ۳۸۱ امتیاز، ۸۹ فالو، ۱۱۵ لایک، ۵۹ کامنت، ۴ گزارش، ۴ درخواست تسویه، ۲ پلن. امتیازها از طریق `PointLedger` ثبت می‌شن و `UserProfile.points` **از روی همون ledger بازمحاسبه** می‌شه، نه دستکاری مستقیم (طبق Constitution بخش ۲).

### بازطراحی پروفایل کاربری
- متن‌های انگلیسی (`Follow`, `Report`, `Recent`, `Who to follow`, `Your points`, …) به فارسی برگردونده شدن — بقیه‌ی سایت فارسیه و این ناهماهنگی بود.
- **تب‌های تقلبی حذف شدند:** `All/Tracks/Playlists/Albums/Reposts` که `href`شون به `#id`هایی اشاره می‌کرد که اصلاً رندر نمی‌شدن — و «Reposts» اصلاً فیچری نیست که در کدبیس وجود داشته باشه.
- عنوان ترک‌ها حالا لینک واقعی به صفحه‌ی ترک‌ان (همین کار باگ #۲۱ رو لو داد).
- دکمه‌ی «درخواست تسویه» برای صاحب پروفایل.

### تایید
- `ruff check .` → **All checks passed**
- `python manage.py test` (SQLite) → **۴۱۶ تست، OK** (۱ skip)
- `python scripts/local_postgres.py test` (PostgreSQL واقعی) → **۴۱۷ تست، OK، بدون skip**
- `manage.py check` / `makemigrations --check --dry-run` → تمیز
- جاروب خودکار **۳۱ مسیر** در سه سطح دسترسی (ناشناس/کاربر/staff) با داده‌ی seed واقعی → هیچ خطای ۴۰۰+
- تایید دستی مرورگر: صفحه‌ی کشف، پروفایل، صفحه‌ی ترک فارسی (باگ #۲۱)، داشبورد پلتفرم، صف تسویه، ادمین، AuditLog، `/healthz/`
- **تایید end-to-end جریان تسویه در مرورگر واقعی:** تایید یک payout ۴۸ امتیازی → ردیف `-48` در `PointLedger` با reason=`PAYOUT_DEDUCTION`، کش و ledger هر دو صفر (بدون drift)، وضعیت `paid`، و `AuditLog` ثبت‌شده — یعنی باگ #۱۷ (امتیاز هرگز کم نمی‌شد) واقعاً بسته شده.

**وضعیت CLAUDE.md:** موارد #۲۱ تا #۲۵ اضافه و بسته شدند. بخش ۷ (دستورات توسعه) با مسیر Postgres واقعی و `seed_demo` به‌روز شد.

---

## [2026-08-20] مورد #۴ کاملاً بسته شد — تایید زنده روی PostgreSQL واقعی + رفع مستندات کهنه

**نوع:** Verification + Docs
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**تصمیم:** کاربر صریحاً خواست «حتی Postgres رو به طور کامل اجرا کن» — یعنی بستن قطعی آخرین یادداشت باز مورد #۴ («اتصال زنده به Postgres واقعی هنوز تست نشده») که از فاز ۱ (۲۰۲۶-۰۸-۱۹) باز مونده بود و در گزارش اجرای خودکار همین روز هم دوباره تایید شد که هنوز کامیت نشده.

**راه‌حل:** به‌جای Docker یا نصب سیستمی PostgreSQL (که هیچ‌کدوم روی این ماشین موجود نبودن)، از پکیج پایتون `pgserver` استفاده شد — یک باینری کامل و مستقل PostgreSQL که بدون دسترسی ادمین/Docker/نصب سیستمی بالا میاد. یک سرور PostgreSQL ۱۶.۲ واقعی و زنده راه‌اندازی شد، پروژه واقعاً در برابرش اجرا شد، و بعد کامل پاک‌سازی شد (این پکیج dependency پروژه نیست، فقط ابزار موقت تایید بود).

**نتایج تایید:**
1. `python manage.py migrate` زیر **هر دو** `config.settings.dev` و `config.settings.prod` — هر ۱۴ اپ، هر migration، روی یک دیتابیس تازه، بدون خطا.
2. **کل ۳۴۲+۱ = ۳۴۳ تست پروژه** (بدون هیچ تغییری، همون تست‌سوییت SQLite) روی همون Postgres واقعی اجرا شد — **همه pass**. همین دقیقاً همون فرآیندیه که باگ #۱۳ (`Sum(boolean)`) رو لو داد — یعنی این تایید صرفاً تشریفاتی نیست، واقعاً مشکل واقعی پیدا می‌کنه.
3. `python manage.py check --deploy` زیر `config.settings.prod` با secret/`ALLOWED_HOSTS` واقعی — تمیز، فقط همون هشدار قدیمی و بی‌خطر `W004` (HSTS).

**یافته جانبی (نه باگ Casset):** باینری `pgserver` دیتابیس timezone (IANA tzdata) رو اصلاً نداشت، پس `SET TIME ZONE 'UTC'` اجباری جنگو fail می‌شد. با کپی‌کردن فایل‌های واقعی tzfile از نصب MinGW64 گیت‌بش (`/mingw64/share/zoneinfo`) رفع شد. این محدودیت مخصوص این ابزار تست موقته — هیچ نصب واقعی PostgreSQL (Docker، apt، سرویس مدیریت‌شده) این مشکل رو نداره.

**رفع مستندات کهنه (کشف‌شده توسط اجرای خودکار همون روز):** بخش ۸ CLAUDE.md هنوز می‌گفت `config/settings.py` «با `raise ImportError` مسدوده» — این دیگه درست نبود، فایل کاملاً حذف شده (commit `ea1d08b`). اصلاح شد.

**فایل‌های تغییرکرده:** فقط مستندات — `CLAUDE.md` (مورد #۴ نهایی شد، بخش ۸ اصلاح شد)، `.casset/state/current.md` (بخش Postgres readiness کاملاً بازنویسی شد). هیچ کد اپلیکیشن تغییر نکرد؛ `config/settings/base.py`/`prod.py`/`.env.example` (سخت‌سازی خودِ Postgres، از قبل نوشته شده در یک session قبلی) در همین commit، جدا از فاز ۴+۵، commit شدن.

**وضعیت CLAUDE.md:** مورد #۴ از «✅ حل‌شده (بدون تست زنده)» به «✅ کاملاً حل‌شده و تست‌شده» ارتقا یافت. بخش ۸ (Architecture Map) اصلاح شد.

---

## [2026-08-20] فاز ۴+۵ ادغام‌شده تحویل شد — موارد #۱۳/#۱۴ بسته شدند + تکمیل کار موازی کامیت‌نشده

**نوع:** Feature + Bugfix + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**تصمیم:** طبق پیشنهاد ادغام فاز ۴ (پخش معتبر) و فاز ۵ (فید/آنالیتیکس/کشف)، این جلسه شروع به ساخت فید شخصی، آنالیتیکس Creator، و Trending هوشمند کرد.

**یافته مهم قبل از کدنویسی:** ممیزی working tree نشون داد یک session موازی دیگه (شبیه Postgres/OTP در فازهای قبل، این‌بار مستند در `## [2026-08-20] اجرای خودکار...` — همین entry، پایین‌تر) از قبل، **بدون commit**، دقیقاً همون فیچرها رو ساخته بود: `explore/views.py::discover_view` فید Follow-based و Trending وزن‌دار به Qualified Play داشت؛ `accounts/views.py::creator_studio_view` شنونده اول‌بار/برگشتی + عملکرد هر ترک داشت. **صفر تست** روی هیچ‌کدوم.

طبق قانون بخش ۲ (بازنویسی ممنوع)، این کد بازنویسی نشد — بازبینی و تکمیل شد:

**۲ باگ واقعی کشف و رفع‌شده (مورد #۱۳/#۱۴ بخش ۳ CLAUDE.md):**
1. `creator_studio_view`: `Sum("point_awarded")` روی یک `BooleanField` — روی SQLite بی‌صدا کار می‌کنه، روی PostgreSQL (محیط production طبق Constitution) با خطای `function sum(boolean) does not exist` fail می‌کنه. با `Count("id", filter=Q(point_awarded=True))` رفع شد.
2. همون view: `my_tracks = list(qs)[:50]` — کل ترک‌های Creator رو بدون `LIMIT` در SQL به حافظه می‌کشید. با جابه‌جایی `[:50]` به داخل کوئری رفع شد.

**اضافه‌شده (بخش واقعاً باقی‌مونده از پیشنهاد):**
- `explore/views.py::discover_view` — بخش «افراد پیشنهادی برای دنبال کردن» (Suggested Creators): کاربرانی با حداقل یک ترک عمومی، به‌ترتیب محبوبیت، به‌استثنای خود کاربر و افراد از‌قبل‌دنبال‌شده — نیمه دوم حلقه Follow (بدون این، کاربر تازه‌وارد هیچ مسیر کم‌اصطکاکی برای اولین Follow نداره)
- `templates/explore/discover.html` — رندر بخش بالا

**تصمیم معماری صریح:** `plays.DailyTrackStat`/`aggregate_stats` عمداً به داشبورد وصل نشد — ابزار عملیاتی معتبره ولی زمان‌بندی نشده؛ وصل‌کردن اجباری بدون نیاز مقیاس واقعی، بهینه‌سازی زودهنگام بود. یک تست پایه براش اضافه شد (۰٪ → پوشش پایه) بدون وصل‌کردنش به هیچ view.

**فایل‌های تغییرکرده/جدید:**
- `accounts/views.py::creator_studio_view` — ۲ باگ بالا رفع شد
- `explore/views.py::discover_view` — `suggested_creators`
- `templates/explore/discover.html` — رندر پیشنهاد Creator
- `explore/tests.py` — از خالی (۰ تست) به ۱۶ تست
- `accounts/tests.py` — ۶ تست جدید برای `creator_studio_view`
- `plays/tests.py` — ۳ تست جدید برای `aggregate_stats`

**تایید:**
- `python manage.py test` → **۳۴۳ تست** (از ۳۱۸)، همه pass
- `test core.tests_smoke`، `makemigrations --check`، `ruff check .`، `manage.py check` — تمیز
- تایید دستی کامل در مرورگر واقعی: فید Follow-based، Trending وزن‌دار، Suggested Creators (به‌درستی کاربر از‌قبل‌دنبال‌شده رو حذف کرد)، و داشبورد Creator بدون خطا

**نکته درباره Branch:** این جلسه روی `auto/2026-08-20-verify-settings-cleanup` شروع شد (branch یک اجرای خودکار قبلی، که دقیقاً به همون commit `stabilization/v1-baseline` اشاره می‌کرد — هیچ commit جدایی نداشت). قبل از commit این فاز، به `stabilization/v1-baseline` سوییچ شد تا با روال فازهای قبلی هماهنگ بمونه.

**نکته باز باقی‌مانده (خارج از scope این commit، طبق همون قانون «فقط چیزی که مال خودته رو دست بزن»):** `config/settings/base.py`/`prod.py` و `.env.example` هنوز شامل سخت‌سازی Postgres کامیت‌نشده‌ای هستن که مستندات (CLAUDE.md مورد #۴) از قبل «✅ حل‌شده» توصیفش می‌کنه — یعنی یک واگرایی واقعی بین مستندات و git history. این سومین باره که این فایل‌ها در طول این گفتگو (فاز ۲، فاز ۳، الان) شناسایی و عمداً دست‌نخورده باقی می‌مونن. توصیه صریح: PYMN باید تصمیم بگیره این commit بشه یا نه — دیگه لازم نیست دوباره کشفش کنیم.

**وضعیت CLAUDE.md:** موارد #۱۳ و #۱۴ بسته شدند ✅. جدول دامنه‌ها: `explore`، `accounts`، `plays` به‌روز شدند. بخش ۶: فاز ۴+۵ ادغام‌شده ✅ بسته شد.

---

## [2026-08-20] اجرای خودکار — تایید حذف `config/settings.py` (از قبل انجام‌شده) + کشف تغییرات کامیت‌نشده

**نوع:** Docs (verification only، بدون تغییر کد)
**انجام‌دهنده:** Claude (scheduled task «casset-autonomous-cycle»، بدون نظارت)
**Branch:** `auto/2026-08-20-verify-settings-cleanup`

**تصمیم:** اولین آیتم `⬜ pending` صف (`.casset/state/task-queue.md`) بررسی/حذف `config/settings.py` بود.

**یافته ۱ (آیتم صف از قبل انجام‌شده):** `config/settings.py` در فایل‌سیستم وجود نداشت. با `git log --diff-filter=D` تایید شد که در commit `ea1d08b` (بدون تاریخ در این اجرا، قبلاً روی `stabilization/v1-baseline` کامیت شده) حذف شده — و آن commit `ancestor` مستقیم `HEAD` فعلی است، یعنی این حذف از قبل روی baseline قرار دارد. گشتم و هیچ `import config.settings` برهنه (غیر از `config.settings.dev`/`.prod`) در `manage.py`، `wsgi.py`، `asgi.py`، `pyproject.toml` یا هیچ اپی پیدا نشد. صف فقط به‌روزرسانی نشده بود؛ در همین اجرا به `🔄 in-review` تغییر کرد.

**یافته ۲ (مهم‌تر، خارج از scope این آیتم، فقط گزارش‌شده نه دست‌زده):** working tree روی `stabilization/v1-baseline` هنگام شروع این اجرا **حاوی تغییرات واقعی کامیت‌نشده** بود (جدا از نویز تفاوت CRLF/LF که تقریباً همه‌ی فایل‌های ردیابی‌شده را پوشانده بود) — با `git diff --ignore-all-space --stat`: ۱۰ فایل، ۵۵۷ خط افزوده/کم‌شده:
`.env.example`, `accounts/tests.py`, `accounts/views.py`, `config/settings/base.py`, `config/settings/prod.py`, `explore/tests.py`, `explore/views.py`, `plays/tests.py`, `templates/accounts/creator_studio.html`, `templates/explore/discover.html`.
نمونه بررسی‌شده: `config/settings/base.py`/`prod.py` دقیقاً همان سخت‌سازی Postgres (`CONN_HEALTH_CHECKS`, `OPTIONS.sslmode`, fail-fast `DB_ENGINE`/`DB_PASSWORD`) است که `CLAUDE.md` مورد #۴ و `current.md` بخش «Postgres readiness» آن را **«✅ حل‌شده»** توصیف می‌کنند — یعنی مستندات ادعای تکمیل و کامیت‌شدن این کار را دارند، ولی کد واقعی هرگز کامیت نشده و فقط در working tree نشسته است. `accounts/views.py` هم شامل فیچر تحلیلی جدید و کامل (اولین‌بار/بازگشتی listener، breakdown هر ترک، فیکس `SUM(boolean)` که روی Postgres واقعی fail می‌کند) است که در هیچ‌جای changelog مستند نشده. **این اجرا این فایل‌ها را دست نزد** (نه commit، نه stash، نه discard) چون خارج از scope آیتم صف بود و تصمیم‌گیری درباره‌ی نگه‌داشتن/دورانداختنشان نیاز به تایید PYMN دارد.

**فایل‌های تغییرکرده در این اجرا:** فقط `.casset/state/task-queue.md` (وضعیت آیتم ۱) + همین entry در `changelog.md`. هیچ کد اپلیکیشن دست نخورد.

**تست:** غیرقابل‌اجرا در این sandbox — پروژه `requires-python = ">=3.12,<3.15"` (`pyproject.toml`) و `Django>=6.0` که خودش `>=3.12` می‌خواهد؛ sandbox فقط Python 3.10.12 دارد و دسترسی root/sudo برای نصب 3.12 وجود ندارد (`apt-get`/`sudo` هر دو رد شدند). این محدودیت شدیدتر از محدودیت‌های قبلی (فقدان Postgres) است — کل تست‌سوییت اصلاً قابل اجرا نبود، نه فقط بخش‌های وابسته به Postgres. تنها تایید انجام‌شده: بررسی استاتیک با `grep` برای رفرنس‌های باقیمانده به ماژول حذف‌شده.

**اثر:** آیتم ۱ صف عملاً بسته است (منتظر تایید ✅ نهایی PYMN). یافته دوم مهم‌تر است: مقداری کار واقعی و به‌ظاهر باکیفیت (سخت‌سازی Postgres که مستندات آن را تمام‌شده می‌دانند + آنالیتیکس creator studio) در خطر از‌دست‌رفتن است چون هرگز کامیت نشده.

**وضعیت CLAUDE.md:** بدون تغییر (طبق قانون اجرای خودکار، این فایل در این مسیر ویرایش نمی‌شود). توجه: بخش ۸ (Architecture Map) هنوز می‌گوید `config/settings.py` «با `raise ImportError` مسدوده» — این دیگر درست نیست (فایل کاملاً حذف شده)؛ نیاز به اصلاح دستی توسط PYMN یا از طریق Skill `casset-sync-docs`.

---

## [2026-08-19] فاز ۳ (اعتماد و امنیت) تحویل شد — موارد #۱۱/#۱۲ بسته شدند + auto-approve

**نوع:** Feature + Architecture + Security + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**تصمیم:** کاربر درخواست فاز ۳ کامل (Trust & Safety) رو داد، به‌همراه یک سوال محصولی: آیا صف بررسی/رد ترک گزینه مناسبیه؟ و یک درخواست مشخص: امکان تایید خودکار پیش‌فرض برای روان‌تر شدن روند سایت. هم‌زمان خواسته شد تمام کد مرده‌ی شناسایی‌شده در بررسی‌های قبلی، بازبینی و یا رفع یا حذف بشه.

**یافته‌های بحرانی (تایید‌شده با خوندن کد، نه فرض):**
1. `moderation/views.py::report_queue` فقط لیست گزارش‌ها رو نشون می‌داد — staff هیچ راهی برای تغییر وضعیت (reviewed/actioned/rejected) نداشت.
2. هیچ مکانیزم تعلیق حساب کاربری در کل پروژه وجود نداشت.
3. `notifications/services.py::check_and_notify_milestone` از فاز ۱ نوشته شده بود ولی **هیچ‌جا صدا زده نمی‌شد** — کد مرده.
4. **یافته امنیتی جدید حین پیاده‌سازی تعلیق:** `django.contrib.auth.login()` خودش `is_active` رو چک نمی‌کنه (برخلاف ورود با رمز که از `ModelBackend.authenticate` رد می‌شه) — یعنی بدون فیکس صریح، `phone_verify_view` (تنها مسیر ورود بدون رمز پروژه) می‌تونست تعلیق حساب رو کامل دور بزنه.

**تصمیم محصولی (auto-approve):** صف بررسی دستی حذف نشد — یک `PlatformSetting.auto_approve_tracks` (پیش‌فرض خاموش) اضافه شد. روشن‌کردنش باعث می‌شه `submit_track` بلافاصله همون `moderation.services.approve_track(actor=None)` رو صدا بزنه که صف استاف هم استفاده می‌کنه — یک پیاده‌سازی مشترک، نه دو مسیر موازی.

**فایل‌های تغییرکرده/جدید:**
- `core/models.py`, `core/admin.py` — `PlatformSetting.auto_approve_tracks` (migration `0002`)
- `moderation/services.py` — بازنویسی کامل: `approve_track`/`reject_track` از views.py منتقل شدن (staff queue و auto-approve حالا یک پیاده‌سازی مشترک دارن)؛ `update_report_status`، `restore_comment`، `suspend_user`/`unsuspend_user` جدید
- `moderation/views.py`, `urls.py` — `update_report`، `restore_comment_view`، `suspend_profile`، `unsuspend_profile`
- `moderation/tests.py` — ۱۹ تست جدید
- `uploads/views.py::submit_track` — چک `auto_approve_tracks`؛ `uploads/tests.py` — ۴ تست جدید
- `accounts/models.py` — `UserProfile.suspended_at`/`suspended_reason` (migration `0002`؛ اجرا از طریق `User.is_active` استاندارد جنگو، نه یک فلگ سفارشی)
- `accounts/views.py::phone_verify_view` — چک صریح `is_active` (فیکس امنیتی بالا)
- `accounts/forms.py::LoginForm` — پیام فارسی برای حساب تعلیق‌شده
- `config/settings/base.py` — `AUTHENTICATION_BACKENDS = ["...AllowAllUsersModelBackend"]` تا پیام فارسی واقعاً نمایش داده بشه (با `ModelBackend` پیش‌فرض، جنگو حساب inactive رو با پیام عمومی «رمز اشتباه» قاطی می‌کنه چون از authenticate() اصلاً User برنمی‌گردونه)
- `accounts/tests.py` — ۲ تست جدید (تعلیق در OTP و در ورود با رمز)
- `interactions/models.py` — `CreatorBlock` (creator, blocked_user) — migration `0002`
- `interactions/services.py` — `toggle_creator_block` + چک block داخل `add_comment`
- `interactions/views.py`, `urls.py` — `api_block`
- `interactions/tests.py` — ۹ تست جدید
- `plays/views.py::register_play` — صدازدن `check_and_notify_milestone` بعد از هر play جدید؛ `plays/tests.py` — ۲ تست جدید
- `templates/moderation/report_queue.html` — بازنویسی کامل با اکشن‌های staff
- `templates/moderation/track_queue.html` — بنر auto-approve
- `templates/tracks/track_detail.html` — دکمه «بلاک» برای صاحب ترک
- `static/app.js` — `handleBlockToggle`
- **حذف:** `templates/tracks/detail.html` — قالب orphan بدون هیچ رفرنس، با مدل کامنت ناهم‌خوان با `Comment` واقعی

**تایید:**
- `python manage.py test` → **۳۱۸ تست** (از ۲۸۶)، همه pass
- `test core.tests_smoke`، `makemigrations --check`، `ruff check .`، `manage.py check` — تمیز
- تایید دستی کامل در مرورگر: staff یک حساب رو تعلیق کرد با یادداشت دلیل → صفحه فوراً «تعلیق‌شده» نشون داد → همون کاربر با رمز درست نتونست وارد بشه و پیام فارسی «این حساب تعلیق شده است» رو دید → بنر auto-approve روی صف ترک درست ظاهر شد → صاحب ترک روی کامنت کاربر دیگه «بلاک» زد و در دیتابیس واقعاً ثبت شد (تایید مستقیم با query)

**اثر:** صف Report دیگه فقط یک ویترین نیست — staff می‌تونه واقعاً تصمیم بگیره. تعلیق حساب اولین بار در پروژه پیاده‌سازی شد، با یک باگ امنیتی واقعی (OTP bypass) که قبل از انتشار پیدا و رفع شد. دو مورد کد مرده (milestone notification، template یتیم) به نتیجه رسیدن — یکی وصل شد، یکی حذف شد.

**وضعیت CLAUDE.md:** موارد #۱۱ و #۱۲ بسته شدند ✅. جدول دامنه‌ها (بخش ۴): `accounts`, `uploads`, `plays`, `interactions`, `moderation` به‌روز شدند. بخش ۶: فاز ۳ ✅ بسته شد.

---

## [2026-08-19] فاز ۲ بازنگری‌شده تحویل شد — موارد #۹/#۱۰ بسته شدند

**نوع:** Feature + Architecture + Tests
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**تصمیم:** طبق بازنگری فاز ۲ (entry قبلی همین روز، بخش ۷ `90-day-roadmap.md`)، دو حفره باز کدنویسی شدند: endpoint‌های اجتماعی گمشده (مورد #۹، بحرانی) و Player UX رقابتی (مورد #۱۰).

**فایل‌های تغییرکرده/جدید:**
- `interactions/services.py` (جدید) — لایه Service طبق قانون بخش ۲: `add_comment`, `delete_comment`, `toggle_comment_like`, `toggle_favorite`؛ کنترل دسترسی (owner/staff، visibility ترک) اینجا تمرکز دارد، نه در view
- `interactions/views.py`, `urls.py` — ۴ endpoint جدید: `POST /api/v1/comment/add/`, `.../<id>/delete/`, `.../<id>/like/`, `POST /api/v1/favorite/`
- `interactions/tests.py` — از خالی به ۳۶ تست (شامل `toggle_like`/`toggle_follow` که تا امروز هم بدون تست بودند)
- `moderation/models.py` — `Report.TargetType.COMMENT` + فیلد `comment` FK (migration `0002_report_comment_alter_auditlog_target_type_and_more`)؛ `AuditLog.TargetType.COMMENT` هم اضافه شد
- `moderation/services.py` (جدید) — `check_and_auto_hide_comment`: بعد از ۳ گزارش باز (pending/reviewed)، کامنت خودکار `is_public=False` می‌شود + یک `AuditLog` ثبت می‌کند؛ ایده‌مپوتنت (کامنت از قبل مخفی → no-op)
- `moderation/views.py`, `urls.py` — `report_comment` (همان الگوی rate-limit روزانه `report_track`/`report_profile`)
- `moderation/tests.py` — ۷ تست جدید برای `report_comment` + auto-hide
- `tracks/views.py::track_detail` — کامنت‌های عمومی (`is_public=True`) + وضعیت Favorite کاربر را به context اضافه می‌کند؛ با `annotate(like_count=Count("likes"))` از N+1 روی هر ردیف کامنت جلوگیری شد
- `templates/tracks/track_detail.html` — دکمه Favorite، دکمه Share (لینک مطلق صفحه)، بخش کامل نظرات (فرم ارسال + لیست + دکمه‌های لایک/حذف/گزارش هر کامنت)
- `static/app.js` — `handleFavorite`, `handleShare` (Web Share API با fallback به clipboard)، `handleCommentSubmit/Like/Delete/Report`، و بخش جدید «Player UX»: `cycleSpeed` (۷ پله ۰.۵x–۲x، ذخیره در `localStorage`)، `hookResumeAndSpeed` (ذخیره/بازیابی موقعیت پخش هر ۵ ثانیه به‌ازای هر `trackId`، صرف‌نظر از اینکه پخش‌کننده Global bar باشد یا Audio داخل صفحه)، `cycleSleepTimer` (پله‌های خاموش/۱۵/۳۰/۴۵/۶۰ دقیقه)
- `templates/base.html` — دکمه‌های `#pbSpeed`/`#pbSleep` در playerbar
- `accounts/views.py::public_profile` — باگ واقعی رفع شد: `stats.likes` همیشه هاردکد `0` بود در حالی که `public_profile_by_handle` (همان صفحه با URL کوتاه) این عدد را درست حساب می‌کرد؛ حالا هر دو مسیر یکسان `Count("likes")` می‌زنند
- `accounts/tests.py` — یک تست رگرسیون برای همین باگ
- `moderation/admin.py` — فیلد `comment` به `ReportAdmin` اضافه شد

**یافته جانبی مهم:** حین بررسی `accounts/views.py` برای مورد Rate-limit سطح IP روی OTP (که در بازنگری فاز ۲ به‌عنوان کار هفته ۴ فرض شده بود)، مشخص شد **این قبلاً پیاده‌سازی شده** (`_rate_limited()` در `phone_start_view`/`phone_verify_view`) — احتمالاً در یک session موازی دیگر. چیزی برایش ساخته نشد؛ فقط سند بازنگری فاز ۲ اصلاح شد تا این واقعیت را منعکس کند.

**یافته code review (قبل از commit):** `toggle_comment_like` فقط `comment.is_public` را چک می‌کرد، نه visibility ترک زیرش — یعنی اگه یک ترک بعداً `private` بشه، بقیه کاربرها همچنان می‌تونستن با صدازدن مستقیم API روی کامنت‌های اون لایک بذارن (دکمه در UI دیده نمی‌شد ولی endpoint باز بود). با فراخوانی همون `_track_visible_to()` که `add_comment`/`toggle_favorite` هم استفاده می‌کنن رفع شد؛ ۲ تست رگرسیون اضافه شد (`interactions/tests.py::CommentLikeViewTests`).

**تایید:**
- `python manage.py test` → **۲۸۶ تست** (از ۲۴۲)، همه pass
- `python manage.py test core.tests_smoke` → ۳۴ تست، pass
- `python manage.py makemigrations --check --dry-run` → «No changes detected»
- `ruff check .` → فقط همان ۴ هشدار cosmetic از قبل موجود در `config/urls.py` (بی‌ربط)
- تایید دستی مرورگر روی `runserver` واقعی با دو کاربر (Creator + Viewer): ورود، ارسال کامنت (ظاهر شدن آنی بدون رفرش)، Favorite toggle (0→1)، تغییر سرعت پخش (1x→1.25x) — همه کار کردند؛ داده‌های seed تست بعد از تایید پاک شدند

**اثر:** فاز ۲ بازنگری‌شده (بخش ۷ `90-day-roadmap.md`) کامل تحویل شد. کامنت/لایک‌کامنت/Favorite — که تا امروز فقط در دیتابیس وجود داشتند و هیچ کاربری نمی‌توانست ازشان استفاده کند — الان یک قابلیت واقعی کاربر است.

**وضعیت CLAUDE.md:** موارد #۹ و #۱۰ بسته شدند ✅. جدول دامنه‌ها (بخش ۴): `interactions` و `moderation` به‌روز شدند. بخش ۶ (مسیر فعلی): فاز ۲ ✅ بسته شد.

---

## [2026-08-19] مورد #۴ — Postgres هاردن شد و فاز ۱ رسماً بسته شد

**نوع:** Architecture + Security + Docs
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**یافته ابتدای بررسی:** جدول بخش ۳ `CLAUDE.md` مورد #۴ را 🟠 باز نشون می‌داد با توضیح *"prod.py تنظیمات Postgres نداره"*. با خوندن کد واقعی مشخص شد این توضیح دیگه درست نیست — `config/settings/base.py` از قبل یک toggle کامل `DB_ENGINE=sqlite|postgresql` داشت (ENGINE/NAME/USER/PASSWORD/HOST/PORT/CONN_MAX_AGE از env، `psycopg[binary]>=3.3` هم در `pyproject.toml` نصب بود) و `prod.py` هم با `from .base import *` اون رو ارث می‌برد. یعنی مستندات کهنه بود، نه کد ناقص. با این حال، بازبینی چند شکاف واقعی معماری/امنیتی رو نشون داد که برای یک استقرار Production حرفه‌ای لازم بودن و رفع شدن.

**فایل‌های تغییرکرده:**
- `config/settings/base.py` — بلوک `DB_ENGINE == "postgresql"`: اضافه شدن `CONN_HEALTH_CHECKS: True` (همراه با `CONN_MAX_AGE` از قبل موجود، جلوی استفاده از یک connection مرده بعد از idle-timeout/failover سرور رو می‌گیره) و `OPTIONS` جدید شامل `sslmode` (از `DB_SSLMODE` env، پیش‌فرض `"prefer"`) و `connect_timeout` (از `DB_CONNECT_TIMEOUT`، پیش‌فرض ۱۰ ثانیه — جلوی hang نامحدود در صورت غیرقابل‌دسترس بودن دیتابیس)
- `config/settings/prod.py` — سه دروازه دفاعی جدید، همون الگوی fail-fast موجود برای `ALLOWED_HOSTS`:
  1. اگه `DB_ENGINE != "postgresql"` باشه → `ImproperlyConfigured` (طبق قانون بخش ۲ Constitution: *"محیط Production باید PostgreSQL باشه، نه SQLite"* — قبلاً این قانون فقط مستند بود، الان enforce می‌شه)
  2. اگه `DB_PASSWORD` خالی باشه → `ImproperlyConfigured` (تا امروز یک پسورد خالی در prod بی‌صدا به Postgres ارسال می‌شد و فقط موقع اتصال واقعی fail می‌کرد، نه در استارت‌آپ)
  3. اگه operator صریحاً `DB_SSLMODE` ست نکرده باشه، پیش‌فرض از `"prefer"` (که اجازه fallback بی‌صدا به اتصال رمزنگاری‌نشده رو می‌ده) به `"require"` ارتقا پیدا می‌کنه — با این حال یک override صریح (مثلاً `disable` روی یک VPC خصوصی مورد اعتماد) همچنان قابل استفاده‌ست
- `.env.example` — مستندسازی `DB_SSLMODE` و `DB_CONNECT_TIMEOUT` با توضیح واضح، و یادآوری اینکه prod حالا `DB_ENGINE=postgresql` + `DB_PASSWORD` غیرخالی رو الزامی می‌کنه
- `CLAUDE.md` — مورد #۴ به ✅ تغییر کرد؛ بخش ۶ (نقشه مسیر) فاز ۱ رو "بسته شد" علامت زد
- `.casset/state/current.md` — Status و critical path به‌روز شد (فاز ۱ ✅، فاز ۲ فعال)

**راستی‌آزمایی انجام‌شده (بدون Postgres واقعی روی این ماشین — نه Docker نه نصب محلی موجود بود):**
1. `manage.py test` (sqlite, dev) → همچنان **۲۴۲ تست، همه pass** — بدون رگرسیون
2. `manage.py check` با `DB_ENGINE=postgresql` شبیه‌سازی‌شده (بدون سرور واقعی) → بدون خطا، یعنی خود منطق ساخت `DATABASES` و import کردن `psycopg` صحیحه
3. تست مستقیم هر ۴ رفتار جدید (نه فقط ادعا):
   - prod + `DB_ENGINE=sqlite` → `ImproperlyConfigured` با پیام واضح ✅
   - prod + `DB_ENGINE=postgresql` بدون `DB_PASSWORD` → `ImproperlyConfigured` ✅
   - prod + پیکربندی کامل معتبر → `check --deploy` تمیز (فقط همون هشدار قدیمی و بی‌خطر `W004` HSTS) ✅
   - `sslmode` در dev = `"prefer"`, در prod بدون override = `"require"`, در prod با `DB_SSLMODE=disable` صریح = `"disable"` ✅ (هر سه حالت با پرینت مستقیم `settings.DATABASES` تایید شد)
4. `makemigrations --check --dry-run` → «No changes detected»
5. `ruff check` روی فایل‌های تغییرکرده → تمیز؛ `ruff check .` کامل روی کل ریپو فقط همون ۴ خطای cosmetic از قبل موجود در `config/urls.py` (بی‌ربط به این تغییر) رو نشون داد

**محدودیت صادقانه:** این راستی‌آزمایی **اتصال زنده و `migrate` واقعی روی یک سرور PostgreSQL در حال اجرا رو تست نکرده** — چون نه Docker و نه نصب محلی Postgres روی این ماشین موجود بود. تنظیمات از نظر منطق/syntax/fail-fast کاملاً تایید شدن، ولی قبل از اولین deploy واقعی روی Production باید یک بار `DB_ENGINE=postgresql` با یک Postgres واقعی (Docker یا سرویس مدیریت‌شده) امتحان بشه: `migrate` + `test core.tests_smoke`.

**وضعیت CLAUDE.md:** مورد #۴ بسته شد ✅ — **هر ۸ مورد جدول بخش ۳ حالا ✅ هستن.**

## نتیجه‌گیری فاز ۱

طبق معیار Done روادمپ (*"پروژه از صفر با یک `.env` بالا میاد، `pytest` پاس می‌شه، فرم آلبوم کرش نمی‌کنه، امتیاز از Ledger میاد نه مستقیم از پروفایل"*) — همه این‌ها تایید شدن. **فاز ۱ (تثبیت پایه) رسماً بسته شد.** فاز ۲ (هویت کاربر + آپلود + انتشار محتوا + پایه Notification) طبق `.casset/execution/90-day-roadmap.md` فاز فعال بعدی است.

---

## [2026-08-19] بازنگری نقشه راه فاز ۲ + کشف حفره اجتماعی (کامنت/لایک‌کامنت/Favorite بدون endpoint)

**نوع:** Docs + Audit
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `CLAUDE.md` — ردیف #۹ و #۱۰ جدید در جدول بخش ۳؛ ردیف `interactions` در جدول بخش ۴ اصلاح شد؛ بخش ۶ (مسیر فعلی) برای فاز ۲ به‌روزرسانی شد
- `.casset/execution/90-day-roadmap.md` — بخش ۷ کاملاً جدید اضافه شد (بازنگری فاز ۲ + تحقیق رقبا)؛ یادداشت ارجاع در ابتدای فاز ۲ اصلی؛ سه آیتم جدید به Icebox (بخش ۵) اضافه شد
- هیچ کد تغییر نکرد — این session فقط ممیزی و مستندسازی بود

**تصمیم:**
درخواست کاربر بررسی کامل فاز ۲ نسبت به نمونه‌سایت‌های مشابه (SoundCloud، Spotify for Creators، شنوتو، کست‌باکس، طاقچه/نوار/فیدیبو) و ارائه‌ی نقشه راه واقع‌بینانه بود. حین ممیزی کد (نه فقط سند)، `interactions/urls.py` بررسی شد.

**یافته بحرانی (تایید‌شده با خوندن کد واقعی):**
`interactions/urls.py` فقط ۲ endpoint دارد (`toggle_like`, `toggle_follow`). مدل‌های `Comment`, `CommentLike`, `TrackFavorite` در دیتابیس کامل‌اند ولی **هیچ view/endpoint‌ای برای ثبت/حذف کامنت، لایک کامنت، یا Favorite کردن ترک وجود ندارد** — سیستم Notification (`track_comment`, `comment_liked`) آماده‌ی گوش‌دادن است ولی هیچ مسیری برای کاربر برای تولید این رویدادها نیست. سند و CLAUDE.md قبلی این app را «کامل‌تر از انتظار» توصیف می‌کردند که فقط در سطح مدل درست بود، نه endpoint.

**یافته دوم:** `static/app.js` سرعت پخش، Resume Position، یا Sleep Timer ندارد — فیچرهایی که رقبای ایرانی (طاقچه/نوار/فیدیبو) به‌عنوان استاندارد پایه ارائه می‌دن.

**اثر:** فاز ۲ به ۴ هفته مشخص با معیار Done دقیق بازتعریف شد (بخش ۷ roadmap). اولویت اول = بستن endpoint اجتماعی، نه فیچر رقابتی جدید.

**وضعیت CLAUDE.md:** ردیف #۹ باز شد 🔴 (بحرانی، اولویت اول فاز ۲)؛ ردیف #۱۰ باز شد 🟡 (پیشنهادی، هفته ۲ فاز ۲).

---

## [2026-08-18] راستی‌آزمایی کامل قبل از push + پاک‌سازی .gitignore

**نوع:** Config + Verification
**انجام‌دهنده:** Claude (session با صاحب پروژه)

**فایل‌های تغییرکرده:**
- `.gitignore` — الگوهای `db.sqlite3.backup*` و `*.zip` اضافه شد (این فایل‌ها قبلاً untracked ولی بدون الگوی گیت‌ایگنور بودن؛ `*.sqlite3` فقط پسوند دقیق را می‌گیرد نه `db.sqlite3.backup_YYYYMMDD_HHMMSS`)

**تصمیم:** طبق چک‌لیست آماده‌سازی release، قبل از push یک دور کامل راستی‌آزمایی اجرا شد: کل تست‌سوییت (بدون تغییر محتوا نسبت به push قبلی)، `check --deploy` با مقادیر واقعی prod، `makemigrations --check`، و `ruff check .`.

**نتیجه راستی‌آزمایی:**
- `python manage.py test core.tests_smoke -v 2` → ۳۴ تست، همه OK
- `python manage.py test` → **۲۳۵ تست، همه OK**
- `python manage.py check --deploy --settings=config.settings.prod` (با `DJANGO_SECRET_KEY` واقعی ۹۶ کاراکتری، `DJANGO_SECURE_SSL_REDIRECT=1`) → فقط یک هشدار خوش‌خیم (`W004` HSTS تنظیم نشده — عمداً به تصمیم دیپلوی واگذار شده)
- `python manage.py makemigrations --check --dry-run` → «No changes detected»
- `ruff check .` → ۹۱ مورد، همه cosmetic (import-sort/unused-import، از قبل شناخته‌شده). یک `F841` جدید (`inv` بلااستفاده در `billing/tests.py`) — بی‌خطر. هیچ `F821`/syntax error نیست.

**اثر:** هیچ فایل سورسی modified/untracked واقعی باقی نمونده بود (همه‌ی کار قبلی این‌ها قبلاً commit/push شده بودن) — فقط `.gitignore` عوض شد تا فایل‌های بکاپ محلی دیگه به‌عنوان untracked ظاهر نشن.

**وضعیت CLAUDE.md:** بدون تغییر (هیچ مورد جدیدی از جدول بخش ۳ باز/بسته نشد؛ مورد #۴ همچنان 🟠 باز — این بازبینی چیزی درباره‌ی Postgres عوض نکرد).

---

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
