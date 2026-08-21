# S12 — آنالیتیکس سازنده + شخصی‌سازی سبک — گزارش اجرا

**تاریخ:** ۲۰۲۶-۰۸-۲۲
**برنچ:** `feature/s12-analytics-personalization` (بر اساس `master` بعد از S11، commit `b41099f`)
**سند مرجع:** `.casset/releases/v2.1.0-phase2-plan.md` §۵ (S12)
**نتیجه‌ی نهایی:** هر ۲ تسک انجام شدند. ۶۹۴ تست روی SQLite (از ۶۶۰ baseline، +۳۴ تست
S12)، ۶۹۵ تست روی PostgreSQL واقعی محلی (تایید کامل، بر خلاف S10/S11 که این بار محیط
اجازه داد)، پوشش تست ۹۳٪ (از ۹۲٪)، `ruff check .` تمیز، `makemigrations --check` بدون
drift، تایید دستی end-to-end در مرورگر برای هر دو تسک.

---

## پیش از شروع — بررسی ساختار فعلی discovery/analytics

طبق درخواست صریح کاربر، قبل از کدنویسی `explore`, `tracks`, `plays` بررسی شدند:

- **`plays`**: `PlaybackSession` (S11) از قبل هر تلاش پخش را با `ip_hash`/`ua_hash`
  (فقط hash‌شده، هرگز خام) ثبت می‌کند. `DailyTrackStat` + `get_creator_stats_series`
  الگوی مرجع aggregation سریع بودند.
- **نکته‌ی کلیدی که مسیر طراحی تسک ۱ را تعیین کرد:** IP و User-Agent خام هیچ‌جای
  کدبیس ذخیره نمی‌شوند — فقط در همان لحظه‌ی request hash می‌شوند
  (`plays/utils.py::ip_hash/ua_hash`). یعنی برای breakdown جغرافیا/دستگاه، استخراج
  باید **همان لحظه‌ی request** (قبل از hash شدن) انجام شود و فقط مقدار derived/coarse
  ذخیره شود — نه یک بازسازی بعدی از hash (که اصلاً غیرممکن است، هش برگشت‌ناپذیر است).
- **`explore`**: `discover_view` از قبل یک نسخه‌ی ابتدایی توصیه («۳ ژانر اخیر کاربر یا
  fallback به trending») داشت — ولی **inline در view**، بدون امتیاز ترکیبی، بدون cache،
  و candidate pool محدود به `genres__in` بدون هیچ وزن‌دهی. این تسک ۲ آن بلوک را کامل
  جایگزین کرد (نه اضافه کرد) — دقیقاً طبق دستور کاربر «Scope Creep ممنوع» تفسیر شد:
  این جایگزینی خودِ کار خواسته‌شده است، نه فیچر اضافه.
- **`tracks`**: بدون تغییر در این اسپرینت — `Genre`/`Track.genres` (M2M) و
  `published_at` مستقیماً توسط هر دو تسک استفاده شدند، بدون نیاز به تغییر مدل.

---

## تسک ۱ — آنالیتیکس عمیق‌تر Creator (جغرافیا/دستگاه)

**فایل‌های تغییریافته:**
- `plays/models.py` — `PlaybackSession.DeviceType` (desktop/mobile/tablet/bot/unknown) +
  فیلدهای `country_code` (CharField(2), خالی=نامشخص)، `device_type`
- `plays/migrations/0006_playbacksession_country_code_and_more.py`
- `plays/geo.py` (جدید) — `resolve_device_type()`, `resolve_country_code()`
- `plays/services.py` — `start_playback_session`/`_touch_session`/`try_award_point`
  وصل شدند؛ تابع جدید `get_creator_geo_device_breakdown()`
- `plays/views.py`, `plays/urls.py` — endpoint جدید `GET /api/v1/creator/stats/geo/`
- `plays/admin.py` — نمایش فیلدهای جدید در `PlaybackSessionAdmin` (read-only)
- `accounts/views.py::creator_studio_view` — `geo_breakdown` به context اضافه شد
- `templates/accounts/creator_studio.html` — دو جدول ساده (کشور/دستگاه)
- `plays/tests.py` — ۲۵ تست جدید

**خلاصه‌ی تصمیم:**

هیچ وابستگی جدید (GeoIP database/کتابخانه) اضافه نشد — دلیل: نصب یک دیتابیس MaxMind
GeoLite2 نیاز به کلید لایسنس، فایل باینری بزرگ، و بروزرسانی دوره‌ای دارد؛ سنگین‌تر از
چیزی است که این تسک نیاز دارد. به‌جایش:

1. **دستگاه** — یک regex ساده و توضیح‌پذیر روی User-Agent (`plays/geo.py`)، دقیقاً
   همان فلسفه‌ی «explainable, not ML» که برای تسک ۲ هم به کار رفت. طبقه‌بندی: bot →
   tablet → mobile → desktop → unknown، به همان ترتیب اولویت (bot باید قبل از mobile
   چک شود چون خیلی از UAهای bot رشته‌ی موبایل‌مانند هم دارند).
2. **کشور** — فقط از یک هدر CDN/reverse-proxy معتبر (`CF-IPCountry`, `X-Country-Code`,
   `X-Geo-Country`) خوانده می‌شود، و **فقط وقتی `TRUST_PROXY_HEADERS=1`** — دقیقاً همان
   گیت امنیتی که `plays/utils.py::get_client_ip` از قبل برای `X-Forwarded-For` دارد
   (موضوع باگ تاریخی #۳۲ در CLAUDE.md). بدون یک پراکسی/CDN قابل‌اعتماد جلوی Casset،
   `country_code` همیشه خالی («نامشخص») می‌ماند — حدس زده نمی‌شود. در محیط dev/test
   (`TRUST_PROXY_HEADERS` پیش‌فرض خاموش) این یعنی کشور همیشه خالی است؛ در تایید دستی
   مرورگر هم دقیقاً همین رفتار مشاهده شد (بخش QA پایین).

**حریم خصوصی (الزام صریح تسک):** `get_creator_geo_device_breakdown()` فقط شمارش
تجمیعی برمی‌گرداند — هرگز `ip_hash`/`ua_hash` یا یک ردیف per-session. این با تست
مستقیم (`test_response_never_contains_raw_hash_fields`,
`test_response_body_never_leaks_raw_ip_or_ua_hash`) تایید شد: یک hash واقعی در دیتابیس
ساخته شد و تست تایید کرد که هرگز در پاسخ سرویس/API ظاهر نمی‌شود.

**Performance:** cache با TTL ۱۵ دقیقه (`plays:geo_device_breakdown:{creator_id}:{days}`)
— دقیقاً هم‌رده‌ی TTL که برای تسک ۲ انتخاب شد. تست `test_result_is_cached_between_calls`
این را با ساختن یک session جدید بین دو فراخوانی و تایید عدم تغییر نتیجه اثبات می‌کند.

---

## تسک ۲ — لایه‌ی توصیه‌ی سبک روی Discover

**فایل‌های تغییریافته:**
- `explore/services.py` — `get_personalized_recommendations()` (+ کمکی‌های
  `_apply_recs_content_type`, `_popular_recent_fallback`)
- `explore/views.py::discover_view` — بلوک inline قدیمی (خطوط ~۱۲۶-۱۵۴) با یک
  فراخوانی سرویس جایگزین شد
- `explore/tests.py` — ۹ تست جدید

**خلاصه‌ی تصمیم:**

امتیاز ترکیبی، کاملاً توضیح‌پذیر (نه یادگیری ماشین — دقیقاً طبق محدودیت صریح کاربر و
`v2.1.0-phase2-plan.md` §۴.۳: «یک لایه‌ی توصیه‌ی سبک... نه AI مولد»):

```
score = 3.0 × (وزن ژانر / بیشترین وزن ژانر کاربر)
      + 1.0 × (play_count / بیشترین play_count در استخر کاندید)
      + 1.5 × 0.5^(روزهای از انتشار / ۱۴)
```

- **وزن ژانر**: از `PlayEvent` خام کاربر (نه فقط Qualified Play — تفاوت عمدی با
  trending: اینجا سیگنال «چه چیزی گوش داده» مهم است، نه «چه چیزی امتیاز گرفته»)،
  با `collections.Counter` در پایتون (نه `annotate(Count(...))` روی M2M که ریسک
  fan-out/محاسبه‌ی غلط دارد — دقیقاً همان الگوی کوئری‌ای که نسخه‌ی قدیمی inline در
  `discover_view` داشت و هرگز تست نشده بود).
- **Candidate pool**: فقط ترک‌هایی که حداقل یک ژانر مشترک با تاریخچه‌ی کاربر دارند
  (`genres__id__in=genre_weights.keys()`) — یعنی فیلتر ژانر همان مرحله‌ی کوئری است،
  نه فقط امتیازدهی؛ یک ترک از ژانر کاملاً نامرتبط هرگز حتی وارد امتیازدهی نمی‌شود.
- **Fallback** (کاربر جدید/ناشناس/بدون کاندید هم‌ژانر): «محبوب‌ترین‌های اخیر» —
  ترک‌های منتشرشده در ۹۰ روز اخیر مرتب‌شده بر اساس `play_count`، و اگر حجم انتشار
  اخیر کم بود (پلتفرم جوان/کم‌فعالیت)، با محبوب‌ترین‌های همه‌ی زمان‌ها پر می‌شود تا
  بخش هرگز خالی‌تر از حد لازم نباشد.
- **Cache**: TTL ۲۰ دقیقه، کلید بر اساس `(user_id یا "anon", content_type, limit)`.

**Performance:** `prefetch_related("genres")` روی base queryset یعنی
`track.genres.all()` داخل تابع امتیازدهی هیچ کوئری اضافه‌ای نمی‌زند (از cache
prefetch می‌خواند). تست `test_query_count_stays_bounded_no_n_plus_one` با
`CaptureQueriesContext` تایید می‌کند تعداد کوئری‌ها یک عدد ثابت کوچک است (≤۱۰)، نه
یک کوئری به‌ازای هر ترک کاندید. `test_cached_call_issues_zero_queries` تایید می‌کند
فراخوانی دوم (کش‌شده) **صفر** کوئری می‌زند.

---

## تست

**افزوده‌شده در این اسپرینت:**
- `plays/tests.py`: ۷ تست `resolve_device_type` (mobile/tablet/desktop/bot/empty
  UA)، ۵ تست `resolve_country_code` (untrusted، Cloudflare header، هدر عمومی، مقدار
  نامعتبر، هدر غایب)، ۲ تست wiring واقعی `register_play` (device_type واقعی از UA،
  country فقط با proxy معتبر)، ۶ تست `get_creator_geo_device_breakdown` (گروه‌بندی،
  bucket نامشخص، جداسازی سازنده‌ها، پنجره‌ی زمانی، عدم نشت hash خام، cache)، ۵ تست
  `api_creator_geo_device` (auth، صحت پاسخ، عدم نشت در بدنه‌ی HTTP خام، clamp پارامتر
  `days`، جداسازی سازنده‌ها). **مجموع: ۲۵ تست.**
- `explore/tests.py`: ۷ تست سرویس (تطابق ژانر، حذف ترک‌های قبلاً پخش‌شده، fallback
  کاربر جدید، fallback ناشناس، cache، دو تست محدودیت کوئری) + ۲ تست یکپارچگی
  `discover_view`. **مجموع: ۹ تست.**
- **جمع کل تست‌های جدید: ۳۴** (۲۵ + ۹) — دقیقاً برابر با افزایش خالص کل سوئیت
  (۶۹۴ − ۶۶۰)، چون هیچ تست موجودی حذف/جایگزین نشد.

**نتایج:**

| مرحله | قبل از S12 | بعد از S12 |
|---|---|---|
| تست روی SQLite | ۶۶۰ (۱ skip) | **۶۹۴ (۱ skip)** |
| تست روی PostgreSQL واقعی | تایید نشد (محدودیت محیطی S10/S11) | **۶۹۵ — تایید کامل، صفر شکست جدید** |
| پوشش تست | ۹۲٪ | **۹۳٪** |
| `ruff check .` | تمیز | **تمیز** |
| `makemigrations --check` | — | **بدون drift** |
| مدل جدید | — | (فیلد به مدل موجود) `PlaybackSession.country_code`, `.device_type` |
| Endpoint جدید | — | `GET /api/v1/creator/stats/geo/` |

**۵ شکست پیش‌موجود، نامرتبط با S12 (افشا نه پنهان‌کاری):**
`core.tests_settings_secrets.ProdSettingsBootTests` (همان ۵ تست مستند در S10/S11) —
`OSError: [WinError 10106]` از Winsock هنگام spawn یک subprocess پایتون کاملاً جدا،
مشکل شبکه‌ی محلی این ماشین ویندوزی. **تایید صریح این اسپرینت:** همین ۵ تست دقیقاً با
همین خطا روی `master` (قبل از هر تغییر S12) هم مستقیماً اجرا و تایید شدند — تصادفی
انتخاب نشدند، واقعاً پیش از S12 هم شکست می‌خوردند. روی CI (لینوکس) این مشکل رخ
نمی‌دهد.

**تایید PostgreSQL واقعی — این بار موفق (بر خلاف S10/S11):**
`.pgdata` محلی از یک سشن قبلی در وضعیت stale/غیرخالی بود (همان کلاس مشکل مستند در
S11)؛ چون این دایرکتوری صراحتاً gitignored و طبق CLAUDE.md «پاک‌کردنش یعنی ریست کامل»
است، حذف و بازسازی شد. بعد از آن `python scripts/local_postgres.py test` کامل و تمیز
اجرا شد: ۶۹۵ تست (یکی بیشتر از SQLite — تست full-text search که فقط روی Postgres
اجرا می‌شود)، همان ۵ شکست پیش‌موجود و نامرتبط، **صفر شکست جدید مرتبط با S12**. هیچ‌کدام
از کد جدید این اسپرینت از SQL خام یا aggregate خاص دیتابیس استفاده نمی‌کند (`Count`
با `filter=Q(...)`، نه `Sum(BooleanField)` — همان کلاس باگ تاریخی #۱۳/#۱۶).

---

## تایید دستی end-to-end در مرورگر

با `python manage.py seed_demo --users 33 --flush-demo` + سرور dev واقعی:

1. **مهاجرت لازم:** `seed_demo`/سرور dev از دیتابیس SQLite دیسک محلی استفاده می‌کنند
   (نه دیتابیس تست) — migration جدید (`0006_...`) باید صریحاً `python manage.py
   migrate plays` اجرا می‌شد تا صفحه‌ی استودیو کرش نکند (`OperationalError: no such
   column`). این یک قدم عادی استقرار است، نه یک باگ.
2. ورود به‌عنوان `demo_31` (سازنده‌ی تاییدشده با آثار منتشرشده) → `/creator/studio/`
   → بخش «جغرافیا و دستگاه شنونده‌ها» با حالت خالی صحیح رندر شد (چون `seed_demo`
   مستقیماً `PlayEvent`/`PointLedger` می‌سازد، نه از مسیر واقعی `register_play`، پس
   هیچ `PlaybackSession`ای برای این سازنده وجود نداشت — رفتار درست، نه باگ).
3. یک پخش واقعی از طریق همان مسیر client-side که پلیر واقعی استفاده می‌کند
   (`fetch("/api/v1/play/", ...)` با هدر User-Agent واقعی مرورگر) روی ترک «زمستان»
   ثبت شد. تایید مستقیم در دیتابیس: `PlaybackSession` جدید با
   `device_type="desktop"` (به‌درستی از User-Agent واقعی Chrome headless استخراج‌شده)
   و `country_code=""` (به‌درستی خالی، چون `TRUST_PROXY_HEADERS` در dev خاموش است).
4. **نکته‌ی عملیاتی واقعی کشف‌شده:** بازخوانی فوری صفحه‌ی استودیو همچنان بخش را خالی
   نشان می‌داد — نه یک باگ کد، بلکه یک اثر جانبی صحیح از `LocMemCache`: کش سرویس
   (تسک ۱، TTL=۱۵ دقیقه) قبلاً یک نتیجه‌ی خالی را در **پردازش سرور dev** کش کرده بود؛
   `cache.clear()` از یک `manage.py shell` جدا این کش را پاک نمی‌کند چون `LocMemCache`
   به‌ازای هر پردازش پایتون جداست. با ری‌استارت سرور dev (کش خالی جدید)، صفحه بلافاصله
   `Desktop → 1` را نشان داد — **دقیقاً رفتاری که کش باید داشته باشد**، و یک یادآوری
   عملیاتی مفید برای استقرار prod (Redis، کش مشترک بین پردازش‌ها/workerها، این مشکل
   آنجا اصلاً رخ نمی‌دهد چون تنها یک نمونه‌ی کش مشترک وجود دارد).
5. `/discover/` به‌عنوان همان کاربر (با تاریخچه‌ی پخش واقعی) → بخش «پیشنهاد برای تو»
   با ۶ ترک متمایز رندر شد، بدون خطا.
6. Logout → `/discover/` به‌عنوان کاربر ناشناس → بخش «پیشنهاد برای تو» همچنان
   غیرخالی رندر شد (مسیر fallback محبوب‌ترین‌های اخیر).
7. `preview_logs` (سرور dev) در طول کل این جلسه: **بدون خطای سرور جدید.**

---

## خلاصه‌ی نهایی

| معیار | قبل از S12 (بعد از S11) | بعد از S12 |
|---|---|---|
| تعداد تست (SQLite) | ۶۶۰ (۱ skip) | **۶۹۴ (۱ skip)** |
| تعداد تست (PostgreSQL واقعی) | تایید نشد | **۶۹۵ — تایید کامل** |
| پوشش تست | ۹۲٪ | **۹۳٪** |
| `ruff check .` | تمیز | **تمیز** |
| `makemigrations --check` | — | **بدون drift** |
| Endpoint جدید | — | `GET /api/v1/creator/stats/geo/` |
| فایل جدید | — | `plays/geo.py` |
| تایید دستی مرورگر | — | کامل، هر دو تسک، شامل کشف یک نکته‌ی عملیاتی واقعی (کش) |

**نکته برای بهینه‌سازی مراحل بعد (S13 و بعدتر):**
- `.pgdata` را طبق CLAUDE.md به‌راحتی می‌توان حذف/بازسازی کرد وقتی stale می‌شود — این
  دیگر یک «محدودیت محیطی حل‌نشدنی» نیست، فقط یک قدم پاک‌سازی یک‌خطی
  (`rm -rf .pgdata`) قبل از `local_postgres.py test`، وقتی initdb با «directory ...
  exists but is not empty» خطا می‌دهد.
- الگوی تایید «پخش واقعی از طریق fetch به همان endpoint که پلیر صدا می‌زند» (به‌جای
  صبر ۵۹ ثانیه‌ی تایمر ضدتقلب واقعی در UI) یک میان‌بر معتبر برای QA مرورگری آینده است
  — همان مسیر HTTP واقعی را تمرین می‌کند، فقط تایمر سمت کلاینت را دور می‌زند، بدون
  دستکاری کد.
- برای QA مرورگری روی هر endpoint کش‌شده (این تسک، یا `get_creator_stats_series`ی
  S11 مشابه)، یادآوری: `cache.clear()` در یک `manage.py shell` جدا **کش سرور dev در
  حال اجرا را پاک نمی‌کند** (`LocMemCache` هر پردازش جداست) — یا سرور را ری‌استارت
  کن، یا TTL کوتاه‌تری برای تست موقت ست کن، یا مستقیماً از همان پردازش سرور دستور
  بده.
- S13 (اتصال بانکی واقعی تسویه) طبق نقشه‌ی فاز ۲ منتظر قرارداد بانکی PYMN است؛ از نظر
  فنی `PointLedger`/`PayoutRequest` از قبل آماده‌اند — کار فنی این آیتم را می‌شود هر
  زمان که قرارداد آماده شد بدون هیچ پیش‌نیاز اضافه‌ای شروع کرد.
