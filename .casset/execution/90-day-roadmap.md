# Casset — نقشه راه اجرایی ۹۰ روزه (نسخه نهایی تایید‌شده)
**نسخه:** 2.0 (بازنگری‌شده با تمرکز بر Retention/Community)
**تاریخ:** مرداد ۱۴۰۵
**وضعیت:** سند رسمی مسیر پروژه — همتراز با Notion "Casset — Project Brain"
**مخاطب:** صاحب پروژه + Claude (در تمام جلسات آینده)

> این سند جایگزین و تکمیل‌کننده نسخه اول تحلیل است. تفاوت اصلی: این نسخه صریحاً Casset را به‌عنوان **پلتفرم ارتباطی مبتنی بر استفاده مداوم (Habitual/Community Platform)** در نظر می‌گیرد، نه فقط یک سایت انتشار محتوا. این یعنی لایه‌ی اجتماعی و اعلان‌رسانی از یک "فیچر اضافه" به یک **رکن اصلی MVP** ارتقا پیدا کرده.

---

## بخش ۱ — بازتعریف محصول: چرا "فقط سایت" کافی نیست

وقتی گفتی *"من صرفاً یک سایت نمی‌خوام، یک مکان ارتباطی می‌خوام که مداوم از برنامه استفاده کنن"* — این یک تغییر مهم در اولویت‌بندیه که باید در معماری و نقشه راه منعکس بشه. تفاوت یک "سایت انتشار محتوا" با یک "پلتفرم با استفاده مداوم" در این چیزهاست:

| ویژگی | سایت ساده | پلتفرم با استفاده مداوم (هدف Casset) |
|---|---|---|
| کاربر چرا برمی‌گرده؟ | فقط وقتی خودش بخواد چیزی پیدا کنه | چون سیستم بهش خبر می‌ده چیزی جدید هست |
| رابطه Creator/Listener | یک‌طرفه (پخش و تمام) | دوطرفه (فالو، کامنت، اعلان، رشد قابل مشاهده) |
| ارزش برای Creator | آمار ساده | حس رشد مداوم + بازخورد واقعی مخاطب |
| نقطه‌ی ورود روزانه | لینک مستقیم | فید فعالیت شخصی‌سازی‌شده |

**نتیجه مستقیم روی معماری:** یک دامنه‌ی جدید باید به لیست دامنه‌های موجود (`accounts, tracks, uploads, plays, moderation, explore, interactions, playlists, billing, subscriptions, core`) اضافه بشه:

### دامنه جدید: `notifications` (یا `engagement`)
مسئولیت‌ها:
- **Notification** (مدل): اعلان درون‌برنامه‌ای (کامنت جدید، فالوور جدید، ترک جدید از Creator دنبال‌شده، تایید/رد محتوا توسط مدیریت، رسیدن به یک نقطه‌عطف آماری)
- **ActivityFeed**: فید شخصی‌سازی‌شده بر اساس Follow (چیزی که کاربر می‌بینه وقتی وارد میشه: "جدیدترین‌ها از کسانی که دنبال می‌کنی")
- زیرساخت ارسال (فعلاً فقط In-App کافیه؛ Email/Push در فازهای بعدی)
- تنظیمات کاربر برای اعلان‌ها (کدوم اعلان‌ها فعال باشن)

خبر خوب: مدل‌های پایه‌ای این لایه (`CreatorFollow`, `Comment`, `CommentLike`, `TrackLike`, `TrackFavorite`) **از قبل در اپ `interactions` وجود دارن و خوب طراحی شدن.** فقط لایه‌ی Notification/Feed روی این پایه کمه.

---

## بخش ۲ — معماری حلقه‌ی تعامل (Engagement Loop) پیشنهادی

```
Creator منتشر می‌کند
        │
        ▼
دنبال‌کنندگان Notification می‌گیرند ──► وارد اپ می‌شوند (نقطه بازگشت #۱)
        │
        ▼
پخش می‌کنند → لایک/کامنت/فالو می‌کنند
        │
        ▼
Creator اعلان دریافت‌های جدید را می‌بیند ──► وارد اپ می‌شود (نقطه بازگشت #۲)
        │
        ▼
داشبورد آمار رشد را می‌بیند → انگیزه انتشار محتوای بعدی
        │
        └──────────────► چرخه از نو تکرار می‌شود
```

این حلقه دقیقاً همون چیزیه که پلتفرم‌های موفق مشابه (SoundCloud، Spotify for Podcasters، Cast Box) رو به "روتین روزانه" کاربر تبدیل می‌کنه، نه فقط یک ابزار.

---

## بخش ۳ — یافته‌های فنی تایید‌شده در کد (بدون تغییر نسبت به بررسی قبلی + موارد جدید)

تمام ۸ مورد بررسی‌شده قبلی (باگ AlbumForm، دوگانگی billing/subscriptions، امتیازدهی مستقیم به‌جای Ledger، نبود Postgres فعال، ناهماهنگی dependency، نبود تست، سالت‌های ناامن پیش‌فرض) **کماکان معتبرند** و در فایل `CLAUDE.md` (ریشه پروژه) به‌صورت زنده نگهداری می‌شن.

**یافته جدید در این بازبینی:**

| # | یافته | اهمیت برای هدف "استفاده مداوم" |
|---|---|---|
| 9 | هیچ مدل Notification/Feed در کل کدبیس وجود نداره | 🔴 بحرانی — بدون این، کاربر هیچ دلیل فعالی برای بازگشت نداره |
| 10 | `interactions` app (Follow/Like/Comment) کامل‌تر از انتظار است ولی به هیچ اعلانی وصل نیست | 🟠 فرصت سریع — زیرساخت آماده است، فقط باید Trigger اضافه بشه |
| 11 | `Comment` مدل `is_public` داره ولی هیچ جریان Moderation برای کامنت وجود نداره (فقط برای Track) | 🟡 ریسک — کامنت مسیر رایج هرزنامه/سوءاستفاده است |

---

## بخش ۴ — نقشه راه اصلاح‌شده ۹۰ روزه (با لایه Engagement ادغام‌شده)

### 🔧 فاز ۱ — تثبیت پایه (روز ۱ تا ۱۴)
بدون تغییر نسبت به نسخه قبلی: رفع ۸ باگ/بدهی شناخته‌شده، اولین تست‌ها، فعال‌سازی Postgres، یکی‌سازی dependency.

**معیار Done فاز ۱:** پروژه از صفر با یک `.env` بالا میاد، `pytest` پاس می‌شه، فرم آلبوم کرش نمی‌کنه، امتیاز از Ledger میاد نه مستقیم از پروفایل.

---

### 👤 فاز ۲ — هویت، انتشار محتوا و **پایه اجتماعی** (روز ۱۵ تا ۳۸)

> **بازنگری ۲۰۲۶-۰۸-۱۹:** بخش بزرگی از این فاز (OTP، Upload+validation، Draft→Publish، مدل/API پایه Notification) زودتر از موعد ساخته شد. یک حفره واقعی هم در ممیزی کد کشف شد که این فاز بازتعریف شد تا اول اون رو ببنده. **جزئیات کامل، تحقیق رقبا، و زمان‌بندی هفته‌به‌هفته در بخش ۷ همین سند.** متن اصلی زیر به‌عنوان مرجع تاریخی حفظ شده.

تغییر نسبت به نسخه قبلی: این فاز حالا شامل ساخت اولیه‌ی دامنه `notifications` هم هست، چون فالو کردن (که بخشی از این فازه) بدون اعلان بی‌معنیه.

- ثبت‌نام/OTP، آنبوردینگ Creator (بدون تغییر)
- Upload Service + اعتبارسنجی فایل واقعی (بدون تغییر)
- جریان Draft → Submit → Publish (بدون تغییر)
- **جدید:** مدل `Notification` پایه + اتصال به رویداد `CreatorFollow` ("X شما را دنبال کرد")
- **جدید:** صفحه‌ی "اعلان‌ها" حداقلی (لیست ساده، خوانده/نخوانده)

**معیار Done فاز ۲:** یک Creator می‌تونه منتشر کنه؛ یک کاربر می‌تونه فالوش کنه و Creator یک اعلان ببینه.

---

### 🛡️ فاز ۳ — مدیریت محتوا (روز ۳۹ تا ۵۲)
- پنل بررسی محتوای `Submitted`
- اتصال `Report`/`AuditLog` به جریان واقعی
- **جدید:** جریان Moderation حداقلی برای کامنت‌ها (گزارش کامنت + مخفی‌کردن خودکار بعد از N گزارش)
- **جدید:** اعلان به کاربر هنگام Approve/Reject شدن محتوا

---

### ▶️ فاز ۴ — پخش معتبر و امتیاز واقعی (روز ۵۳ تا ۷۳) — مهم‌ترین فاز محصول
بدون تغییر نسبت به نسخه قبلی از نظر فنی (PlaybackSession/PlaybackEvent، Qualified Play سمت سرور، PointLedger)، با یک افزودنی:
- **جدید:** اعلان "نقطه‌عطف" به Creator (مثلاً هر ۱۰۰ پخش معتبر، یک اعلان تبریک/گزارش کوتاه) — این دقیقاً چیزیه که Creator رو برای انتشار بعدی ترغیب می‌کنه.

---

### 📈 فاز ۵ — آنالیتیکس، فید فعالیت، و کشف محتوا (روز ۷۴ تا ۸۷)
تغییر بزرگ نسبت به نسخه قبلی: این فاز حالا **فید فعالیت شخصی‌سازی‌شده** (Activity Feed بر اساس Follow) رو هم شامل می‌شه — این قلب "استفاده مداوم" است.

- داشبورد Creator (نمودار پخش، امتیاز، دنبال‌کننده - از `DailyTrackStat`)
- **جدید و کلیدی:** صفحه‌ی اصلی/Feed که بر اساس Follow کاربر، جدیدترین محتوای Creatorهای دنبال‌شده رو نشون می‌ده (نه صرفاً یک لیست همگانی)
- Explore/جستجوی پایه (ژانر/تگ)
- Trending ساده مبتنی بر داده واقعی

**معیار Done فاز ۵:** وقتی کاربر لاگین می‌کنه، بدون جستجو، محتوای مرتبط با علاقه‌مندی‌هاش (از طریق Follow) رو می‌بینه.

---

### 🚀 فاز ۶ — سخت‌سازی و استقرار (روز ۸۸ تا ۹۰)
بدون تغییر نسبت به نسخه قبلی: Object Storage، تنظیمات امنیتی نهایی، بک‌آپ، Health Check، استقرار روی دامنه واقعی.

> **نکته صادقانه درباره‌ی جدول‌بندی:** فشرده‌سازی فاز ۵ و اضافه‌کردن Feed/Notification به ۹۰ روز فشرده‌تره. اگه در میانه راه دیدیم زمان کم میاد، اولویت اول حفظ **فاز ۱، ۲ (نسخه پایه)، ۴** است (چون بدون این‌ها محصول اصلاً کار نمی‌کنه)، و فید/اعلان پیشرفته می‌تونه به هفته‌های ۱۳-۱۴+ (کمی بعد از ۹۰ روز) منتقل بشه. این نوع اولویت‌بندی رئال، بهتر از قول‌دادن چیزی است که شکسته تحویل داده بشه.

---

## بخش ۵ — چیزهایی که عمداً از MVP حذف شدن (Icebox)

اینا رو یادداشت کردم که در طول کار وسوسه نشیم اضافه‌شون کنیم، ولی فراموش هم نشن:

- سیستم توصیه‌گر هوشمند (AI Recommendation)
- چت خصوصی بین کاربران
- اعلان Push موبایل / اپلیکیشن نیتیو (فعلاً وب کافیه)
- مارکت‌پلیس و پرداخت پیچیده به Creator (Payout زیرساختش در `billing.PayoutRequest` هست ولی فعال‌سازی کامل بعد از MVP)
- سیستم Badge/Gamification پیشرفته (می‌تونه بعداً روی PointLedger سوار بشه)
- زیرساخت توزیع‌شده/Microservices
- **(افزوده ۲۰۲۶-۰۸-۱۹)** Import/Export فید RSS پادکست (تعامل‌پذیری با کست‌باکس و مشابه) — جذاب ولی زودتر از تثبیت هویت محتوایی Casset معنا نداره
- **(افزوده ۲۰۲۶-۰۸-۱۹)** دانلود آفلاین کامل فایل — نیاز به تصمیم محصولی/امنیتی مجزا درباره DRM دارد، فعلاً فقط Resume Position (سمت کلاینت) کافیه
- **(افزوده ۲۰۲۶-۰۸-۱۹)** چت/کامیونیتی نوع Discord — Scope Creep واضح، رد شد در بررسی رقبا

---

## بخش ۶ — نحوه استفاده از این سند در آینده

1. **در این ریپازیتوری:** فایل `CLAUDE.md` در ریشه پروژه، خلاصه‌ی زنده و همیشه‌به‌روز این سند رو نگه می‌داره. Claude Code / Claude Desktop به‌صورت خودکار این فایل رو در ابتدای هر جلسه می‌خونه.
2. **در Notion:** همین سند به‌صورت کامل، به عنوان صفحه‌ی رسمی "۰۹ — نقشه راه اجرایی ۹۰ روزه" زیر Project Brain ثبت شده. این نسخه، مرجع رسمی مدیریتی است.
3. **در claude.ai (وب/موبایل، خارج از این ریپازیتوری):** اگه بخوای بدون دسترسی فایل هم Claude زمینه کامل پروژه رو داشته باشه، از قابلیت **Projects** در claude.ai استفاده کن: یک Project جدید بساز، این سند رو (یا خلاصه‌اش) در "Project instructions" بذار. اینطوری هر چت جدید داخل اون Project، خودکار این زمینه رو داره — نیازی به تکرار نیست.

---

## بخش ۷ — بازنگری فاز ۲ بر اساس ممیزی کد و تحقیق رقبا (۲۰۲۶-۰۸-۱۹)

### ۷.۱ چرا این بازنگری لازم شد
در فاصله‌ی نوشتن نسخه اول این سند تا الان، بخش بزرگی از محتوای فاز ۲ اصلی (OTP، Upload Service + اعتبارسنجی، جریان Draft→Submit→Publish، مدل و API پایه Notification با ۸ verb) زودتر از موعد و به‌صورت جانبی حین کار روی فاز ۱ ساخته شد (رجوع کن به `.casset/state/changelog.md`, entryهای مربوط به موارد #۱، #۳، #۶، #۷، #۸ بخش ۳ CLAUDE.md). بنابراین فاز ۲ باید بازتعریف بشه: نه «ساختن از صفر»، بلکه «بستن حفره‌های واقعی باقی‌مانده + رقابتی‌سازی هدفمند».

### ۷.۲ یافته بحرانی جدید (تایید‌شده با خوندن کد واقعی، نه فرض)
`interactions` app (لایک/فالو/کامنت/Favorite) از نظر مدل کامل است، ولی `interactions/urls.py` فقط ۲ مسیر دارد: `toggle_like`، `toggle_follow`. **هیچ endpoint‌ای برای ثبت/حذف کامنت، لایک کامنت، یا Favorite کردن ترک وجود ندارد.** یعنی سیستم Notification (ازجمله verbهای `track_comment` و `comment_liked`) آماده‌ی گوش‌دادن به این رویدادهاست، ولی هیچ مسیری برای کاربر برای تولیدشون نیست. این جزو مورد #۹ جدول بخش ۳ CLAUDE.md ثبت شده و **مهم‌ترین بدهی فاز ۲ است — مهم‌تر از هر فیچر رقابتی جدید.**

همچنین `static/app.js` بررسی شد: پلیر فعلی هیچ‌کدام از سرعت پخش، Resume Position، یا Sleep Timer را ندارد (مورد #۱۰ جدول بخش ۳) — این‌ها در هیچ فازی از سند اصلی هم نبودن.

### ۷.۳ خلاصه تحقیق رقبا
| پلتفرم | نکته کلیدی قابل استفاده برای Casset |
|---|---|
| SoundCloud (۲۰۲۵-۲۶) | فید اجتماعی «چی دوستات گوش می‌دن» (Liked by Your Crew)، پلی‌لیست دوستانه؛ انتشار منظم هفتگی → ۶۰٪ retention بیشتر |
| Spotify for Creators (جانشین Anchor) | استاندارد Play فقط بعد از ۳۰ ثانیه گوش‌دادن واقعی (مفهوم نزدیک به Qualified Play خودمون)؛ تفکیک آنالیتیکس شنونده اول‌بار/برگشتی، مقایسه عملکرد اپیزود به اپیزود |
| شنوتو | اکوسیستم صوت کامل (پادکست+کتاب‌صوتی+دوره) + marketplace برای Creator، مدل freemium |
| کست‌باکس | سادگی + امکان کامنت + نوتیف = دلیل اصلی محبوبیتش بین پادکسترهای فارسی با وجود بین‌المللی بودن |
| طاقچه/نوار/فیدیبو | سرعت پخش، تایمر خواب، آفلاین، ادغام کتاب‌صوتی+پادکست زیر یک اشتراک — انتظار پایه‌ی کاربر ایرانی از یک اپ صوتی جدی |
| صنعت gamification عمومی | Badge/Streak عمومی و قابل‌مشاهده → ماندگاری ~۳۴٪ بیشتر نسبت به نسخه خصوصی؛ فقط بعد از تثبیت کامل `PointLedger` معنا دارد |

### ۷.۴ فیچرهای جدید پیشنهادی — دسته‌بندی‌شده

**دسته A — همین فاز ۲ (کم‌هزینه، اثر مستقیم روی «چرا کاربر برگرده»):**
- تکمیل endpoint‌های واقعی کامنت / لایک‌کامنت / Favorite (بحرانی‌ترین آیتم — مورد #۹)
- سرعت پخش پلیر (۰.۵x–۲x)
- Resume Position (ادامه پخش از جایی که رها شده)
- Sleep Timer
- لینک اشتراک‌گذاری ترک/آلبوم/پروفایل Creator (share)

**دسته B — مدل داده‌اش را از الان لحاظ کن، پیاده‌سازی کامل در فاز ۴/۵:**
- آنالیتیکس شنونده اول‌بار/برگشتی (روی `PlaybackEvent`/`DailyTrackStat` موجود سوار می‌شه)
- نسخه‌ی سبک «دوستانت چی گوش می‌دن» — همون Activity Feed فاز ۵، فقط با این الهام طراحی بشه
- Trending واقعی مبتنی بر داده (از قبل در فاز ۵ سند هست، بدون تغییر)

**دسته C — Icebox آگاهانه (اضافه به بخش ۵، فعلاً رد کن):**
- Badge/Gamification پیشرفته روی `PointLedger` — بعد از تثبیت کامل Ledger در فاز ۴ معنا دارد
- Import/Export فید RSS پادکست (تعامل‌پذیری با کست‌باکس و مشابه)
- دانلود آفلاین کامل فایل (تصمیم محصولی/امنیتی مجزا درباره DRM لازم دارد)
- چت/کامیونیتی نوع Discord — Scope Creep واضح طبق قانون CLAUDE.md، رد شد

### ۷.۵ زمان‌بندی فاز ۲ بازنگری‌شده (همان بازه روز ۱۵-۳۸، محتوا بازتعریف‌شده) — ✅ همه تحویل شد (۲۰۲۶-۰۸-۱۹)

| هفته | محور | خروجی مشخص | وضعیت |
|---|---|---|---|
| هفته ۱ (روز ۱۵-۲۱) | بستن حفره اجتماعی | endpoint واقعی ثبت/حذف کامنت، لایک/آنلایک کامنت، Favorite/آنفیوریت ترک — هرکدام با تست + اتصال به Notification موجود | ✅ `interactions/services.py` + ۴ endpoint + ۳۴ تست |
| هفته ۲ (روز ۲۲-۲۸) | Player UX رقابتی | سرعت پخش، Resume Position، Sleep Timer — روی `static/app.js` موجود، بدون بازنویسی پلیر | ✅ سه فیچر در `static/app.js` + دکمه‌های `#pbSpeed`/`#pbSleep` در `templates/base.html`؛ در مرورگر تایید شد |
| هفته ۳ (روز ۲۹-۳۳) | اشتراک‌گذاری + پروفایل عمومی | لینک share برای ترک/آلبوم/پروفایل Creator؛ بهبود `artist_profile.html` با شمارنده‌های اجتماعی واقعی (فالوور/لایک/کامنت) | ✅ دکمه Share (Web Share API + clipboard fallback) در `track_detail.html`؛ باگ `public_profile()` که `likes` را همیشه ۰ نشان می‌داد رفع شد |
| هفته ۴ (روز ۳۴-۳۸) | سخت‌سازی + بستن بدهی باز | rate-limit سطح IP روی تایید OTP؛ پوشش تست `interactions/views.py`؛ Moderation-lite کامنت (گزارش + مخفی خودکار بعد N گزارش) | ✅ Moderation-lite ساخته شد (آستانه ۳ گزارش، `moderation/services.py`)؛ پوشش تست `interactions` از ۰ تست به ۳۴ تست رسید. **rate-limit OTP از قبل در `accounts/views.py::_rate_limited` وجود داشت** — حین بررسی کد کشف شد که این بخش زودتر از موعد (در یک session موازی) انجام شده بود، پس چیزی برایش ساخته نشد. |

### ۷.۶ معیار Done فاز ۲ بازنگری‌شده — همه برآورده شد
۱. ✅ Creator منتشر می‌کند؛ کاربر فالوش می‌کند و Creator اعلان می‌بیند (از قبل برقرار بود)
۲. ✅ کاربر واقعاً روی یک ترک کامنت می‌گذارد و صاحب ترک اعلان می‌گیرد — در مرورگر با کاربر واقعی تایید شد
۳. ✅ کاربر سرعت پخش را عوض می‌کند، Sleep Timer می‌گذارد، و پخش از جایی که قطع کرده ادامه پیدا می‌کند
۴. ✅ لینک ترک بیرون از اپ باز و پخش می‌شود (دکمه Share)
۵. ✅ `interactions` پوشش تست کامل دارد (۳۴ تست جدید، قبلاً صفر)
۶. ✅ کامنت هرزنامه/توهین‌آمیز قابل گزارش و بعد از ۳ گزارش خودکار مخفی می‌شود

> مورد #۴ سند (Postgres) جزو فاز ۲ نبود — طبق جدول بخش ۳ CLAUDE.md مستقلاً بسته شده (یادداشت باز: اتصال به یک Postgres واقعی هنوز smoke-test نشده، قبل از اولین deploy واقعی انجام شود).

### ۷.۸ خلاصه تحویل فاز ۲ (۲۰۲۶-۰۸-۱۹)

**کد جدید:**
- `interactions/services.py` (جدید) — `add_comment`, `delete_comment`, `toggle_comment_like`, `toggle_favorite`
- `interactions/views.py` + `urls.py` — ۴ endpoint جدید (`api_comment_add`, `api_comment_delete`, `api_comment_like`, `api_favorite`)
- `moderation/services.py` (جدید) — `check_and_auto_hide_comment` (آستانه ۳ گزارش)
- `moderation/models.py` — `Report.TargetType.COMMENT` + فیلد `comment` (migration `0002`)
- `moderation/views.py` + `urls.py` — `report_comment`
- `tracks/views.py::track_detail` — کامنت‌ها + favorite state را به context اضافه کرد (بدون N+1 — `annotate(like_count=Count("likes"))`)
- `templates/tracks/track_detail.html` — بخش نظرات، دکمه Favorite، دکمه Share
- `static/app.js` — کنترل سرعت پخش، Resume Position (localStorage)، Sleep Timer، هندلرهای کامنت/فیوریت/شیر
- `templates/base.html` — دکمه‌های `#pbSpeed`/`#pbSleep` در playerbar
- `accounts/views.py::public_profile` — باگ `likes: 0` هاردکدشده رفع شد

**تست:** ۲۴۲ → **۲۸۶ تست** (۴۴ تست جدید: interactions ۳۶ + moderation ۷ + accounts ۱ رگرسیون)، همه سبز. `test core.tests_smoke`، `makemigrations --check`، `ruff check .`، `manage.py check` همه تمیز.

**یافته code review (قبل از commit):** `toggle_comment_like` visibility ترک زیر کامنت را چک نمی‌کرد (فقط `is_public` کامنت) — روی ترک `private`شده بعداً، لایک کامنت از طریق API مستقیم هنوز ممکن بود. با `_track_visible_to()` (همون تابعی که `add_comment`/`toggle_favorite` استفاده می‌کنن) رفع شد + ۲ تست رگرسیون.

**تایید دستی مرورگر:** با دو کاربر واقعی (Creator + Viewer) — ورود، ارسال کامنت (بدون رفرش صفحه ظاهر شد)، Favorite toggle، تغییر سرعت پخش (۱x → ۱.۲۵x) — همه در `http://localhost:8000` تایید شد.

### ۷.۷ منابع تحقیق رقبا
- [SoundCloud drops 4 new features for artists and fans in 2025 — RouteNote](https://routenote.com/blog/soundcloud-drops-4-new-features-for-artists-and-fans-in-2025/)
- [Introducing a New Standard for Podcast Plays and Upgraded Creator Analytics — Spotify Newsroom](https://newsroom.spotify.com/2026-06-11/spotify-for-creators-tools-plays-analytics-updates/)
- [Shenoto provides detailed insight into the Persian podcast industry — Podnews](https://podnews.net/press-release/persian-podcasts)
- [بهترین پادکست‌های فارسی — چطور](https://www.chetor.com/229339-%D8%A8%D9%87%D8%AA%D8%B1%DB%8C%D9%86-%D9%BE%D8%A7%D8%AF%DA%A9%D8%B3%D8%AA-%D9%87%D8%A7%DB%8C-%D9%81%D8%A7%D8%B1%D8%B3%DB%8C/)
- [نوار به اکوسیستم طاقچه پیوست — Taaghche Blog](https://taaghche.com/blog/1405/04/08/%D9%86%D9%88%D8%A7%D8%B1-%D8%A8%D9%87-%D8%A7%DA%A9%D9%88%D8%B3%DB%8C%D8%B3%D8%AA%D9%85-%D8%B7%D8%A7%D9%82%DA%86%D9%87-%D9%BE%DB%8C%D9%88%D8%B3%D8%AA/)
- [10 Examples of Badges Used in Gamification — Trophy.so](https://trophy.so/blog/badges-feature-gamification-examples)

---

## بخش ۸ — فاز ۳: اعتماد و امنیت (Trust & Safety) — ✅ تحویل شد (۲۰۲۶-۰۸-۱۹)

### ۸.۱ چرا این فاز
بررسی کد قبل از شروع نشون داد صف بررسی/تایید/رد ترک و گزارش کامنت/ترک/پروفایل از قبل کار می‌کردن، ولی دو حفره واقعی وجود داشت: **staff هیچ اکشنی روی Report نداشت** (فقط لیست می‌دید، نمی‌تونست reviewed/actioned بزنه)، و **هیچ مکانیزم تعلیق حساب کاربری وجود نداشت**. همچنین `notifications.services.check_and_notify_milestone` از زمان ساخت اپ Notification (فاز ۱) نوشته شده بود ولی هیچ‌جا صدا زده نمی‌شد — کد مرده، دقیقاً همون الگوی کامنت در فاز ۲.

کاربر پروژه هم‌زمان یک سوال محصولی مطرح کرد: آیا صف بررسی/رد ترک گزینه مناسبیه؟ و درخواست داد یک گزینه اضافه بشه که صف به‌صورت پیش‌فرض روی تایید خودکار باشه تا روند سایت روان‌تر باشه.

### ۸.۲ تصمیم محصولی: Auto-approve به‌عنوان یک Toggle، نه جایگزین صف
صف بررسی دستی (`track_queue.html`) به قوت خودش باقی موند — برای پلتفرمی که به «آمار پخش قابل‌اعتماد» و کیفیت محتوا حساسه، بررسی انسانی هنوز گزینه امن پیش‌فرضه. اما یک تنظیم جدید platform-wide اضافه شد: `PlatformSetting.auto_approve_tracks` (پیش‌فرض خاموش). وقتی روشنه، `submit_track` به‌جای گذاشتن ترک روی `SUBMITTED`، بلافاصله همون منطق `approve_track` استاف رو صدا می‌زنه (`actor=None` یعنی سیستمی) — یعنی صف بررسی همچنان وجود داره و در هر لحظه قابل خاموش‌کردنه، بدون این‌که ترک‌های قبلی یا جریان دستی خراب بشه.

### ۸.۳ کد جدید
- `core/models.py` — `PlatformSetting.auto_approve_tracks` (BooleanField) + admin fieldset «Moderation»
- `moderation/services.py` — بازنویسی کامل: `approve_track`/`reject_track` از views.py به اینجا منتقل شدن (staff queue و مسیر auto-approve حالا دقیقاً یک پیاده‌سازی دارن)؛ `update_report_status`، `restore_comment`، `suspend_user`/`unsuspend_user` جدید — همه با AuditLog
- `moderation/views.py` + `urls.py` — `update_report`، `restore_comment_view`، `suspend_profile`، `unsuspend_profile`
- `uploads/views.py::submit_track` — چک `auto_approve_tracks` و صدازدن `moderation.services.approve_track(actor=None)`
- `accounts/models.py` — `UserProfile.suspended_at`/`suspended_reason` (metadata حسابرسی؛ منبع حقیقت اجرا خود `User.is_active` استانداردِ جنگو است)
- `accounts/views.py::phone_verify_view` — **یافته امنیتی حین پیاده‌سازی:** `django.contrib.auth.login()` خودش `is_active` رو چک نمی‌کنه (برخلاف `ModelBackend.authenticate` برای ورود با رمز) — بدون این فیکس، یک حساب تعلیق‌شده می‌تونست از مسیر OTP (تنها مسیر بدون رمز پروژه) دوباره وارد بشه. اضافه شد.
- `config/settings/base.py` — سوییچ به `AllowAllUsersModelBackend` تا پیام فارسی واضح «این حساب تعلیق شده است» واقعاً نمایش داده بشه (با `ModelBackend` پیش‌فرض، جنگو حساب غیرفعال رو با پیام عمومی «نام کاربری/رمز اشتباه» قاطی می‌کنه چون اصلاً User برنمی‌گردونه)
- `accounts/forms.py::LoginForm` — پیام فارسی برای `error_messages["inactive"]`
- `interactions/models.py` — `CreatorBlock` (creator, blocked_user) — مدل جدید برای «بلاک کامنت‌گذار مزاحم از ترک‌های خودم»
- `interactions/services.py` — `toggle_creator_block` + چک `CreatorBlock` داخل `add_comment` (reason=`blocked`)
- `interactions/views.py` + `urls.py` — `api_block`
- `plays/views.py::register_play` — صدازدن `check_and_notify_milestone` بعد از هر افزایش واقعی `play_count` (رفع کد مرده)
- **حذف کد مرده:** `templates/tracks/detail.html` — قالب orphan که هیچ view ای رندرش نمی‌کرد و مدل کامنتش (`c.user`/`c.text`) اصلاً با مدل واقعی `Comment` (`author`/`body`) هم‌خونی نداشت؛ حذف کامل به‌جای نگه‌داشتن کد بلااستفاده

### ۸.۴ فرانت‌اند (تغییرات کوچک ولی مشهود)
- `templates/moderation/report_queue.html` — بازنویسی کامل: هر گزارش حالا دراپ‌داون تغییر وضعیت، دکمه «بازگردانی کامنت» (برای گزارش‌های کامنت مخفی‌شده)، و دکمه «تعلیق حساب»/«رفع تعلیق» (برای گزارش‌های پروفایل، با ورودی دلیل) داره
- `templates/moderation/track_queue.html` — بنر هشدار وقتی auto-approve روشنه («این صف فقط محتوای قدیمی‌تر رو نشون می‌ده»)
- `templates/tracks/track_detail.html` — دکمه «بلاک @username» روی کامنت‌های دیگران، فقط برای صاحب ترک
- `static/app.js` — `handleBlockToggle`

### ۸.۵ تست و تایید
- ۲۸۶ → **۳۱۸ تست** (۳۲ تست جدید)، همه سبز
- `test core.tests_smoke`، `makemigrations --check`، `ruff check .`، `manage.py check` — همه تمیز
- تایید دستی کامل در مرورگر روی `runserver` واقعی: staff یک حساب رو تعلیق کرد → همون کاربر نتونست با رمز عبور وارد بشه (پیام فارسی واضح دیده شد) → بنر auto-approve روی صف ترک درست نشون داده شد → صاحب ترک روی کامنت یک کاربر دیگه کلیک «بلاک» زد و در دیتابیس واقعاً ثبت شد

### ۸.۶ معیار Done فاز ۳ — همه برآورده شد
۱. ✅ staff می‌تواند وضعیت هر Report را عوض کند (نه فقط ببیند)
۲. ✅ حساب کاربری قابل تعلیق/رفع‌تعلیق است و تعلیق هر دو مسیر ورود (OTP + رمز) را واقعاً می‌بندد
۳. ✅ کامنت auto-hide شده توسط staff قابل بازگردانی است
۴. ✅ `PlatformSetting.auto_approve_tracks` صف بررسی را (اختیاری) دور می‌زند بدون حذف صف
۵. ✅ یک کاربر می‌تواند کامنت‌گذار مزاحم را از ترک‌های خودش بلاک کند
۶. ✅ اعلان نقطه‌عطف پخش واقعاً برای Creator ارسال می‌شود
۷. ✅ هیچ کد مرده‌ی شناسایی‌شده‌ای بدون تصمیم (رفع یا حذف) باقی نماند

---

## بخش ۹ — فاز ۴+۵ ادغام‌شده: فید شخصی، آنالیتیکس، کشف هوشمند — ✅ تحویل شد (۲۰۲۶-۰۸-۲۰)

### ۹.۱ یافته مهم قبل از کدنویسی: نیمی از این فاز از قبل ساخته شده بود
قبل از شروع، ممیزی کامل کد نشون داد یک session موازی دیگه (همون الگوی Postgres/OTP rate-limit در فازهای قبل) از قبل، **بدون commit**، دقیقاً همون چیزی رو ساخته بود که این فاز پیشنهاد می‌داد: فید خانه بر اساس Follow (`explore/views.py::discover_view` → `followed_feed`)، Trending وزن‌دار به Qualified Play (`point_awarded=True` به‌جای شمارش خام)، و در `accounts/views.py::creator_studio_view` شنونده اول‌بار/برگشتی + مقایسه ترک‌به‌ترک. این کد **صفر تست** داشت.

به‌جای بازنویسی، این کار طبق قانون بخش ۲ (بازنویسی ممنوع) بازبینی شد — دو باگ واقعی پیدا و رفع شد (مورد #۱۳/#۱۴ بخش ۳ CLAUDE.md)، بعد فقط قسمت واقعاً باقی‌مونده (Suggested Creators) اضافه شد و کل مسیر با تست کامل پوشش داده شد.

### ۹.۲ باگ‌های واقعی کشف‌شده حین ممیزی
1. **`Sum("point_awarded")` روی `BooleanField`** — روی SQLite (محیط dev) بی‌صدا کار می‌کنه چون SQLite بولین رو به‌عنوان عدد ذخیره می‌کنه، ولی روی PostgreSQL (محیط واقعی production طبق Constitution) خطای `function sum(boolean) does not exist` می‌ده. یعنی داشبورد Creator در production کرش می‌کرد. با `Count("id", filter=Q(point_awarded=True))` جایگزین شد — قابل‌حمل و هم‌معنا («چند تا از پخش‌های امروز واجد شرایط بودن»).
2. **`my_tracks = list(qs)[:50]`** — کل ترک‌های یک Creator رو (بدون `LIMIT` در SQL) به حافظه می‌کشید، بعد ۵۰ تای اول رو در پایتون می‌گرفت. برای یک Creator پرکار، یعنی fetch کامل بی‌مورد از دیتابیس. با جابه‌جایی `[:50]` به داخل کوئری (`list(qs[:50])`) رفع شد — حالا `LIMIT 50` در SQL اجرا می‌شه.

### ۹.۳ چیزی که واقعاً اضافه شد (Suggested Creators)
`discover_view` یک بخش «افراد پیشنهادی برای دنبال کردن» جدید داره: کاربرانی که حداقل یک ترک APPROVED+PUBLIC منتشر کردن، به‌ترتیب `follower_count`، به‌استثنای خود کاربر و کسانی که از قبل دنبال می‌کنه. این نیمه‌ی دوم حلقه‌ی «دلیل برگشت» است — `followed_feed` فقط وقتی محتوا داره که از قبل کسی رو دنبال کرده باشی؛ کاربر تازه‌وارد بدون این بخش هیچ مسیر کم‌اصطکاکی برای اولین Follow نداره.

### ۹.۴ تصمیم معماری صریح: `DailyTrackStat`/`aggregate_stats` عمداً وصل نشد
`plays.DailyTrackStat` و دستور `aggregate_stats` از قبل در کدبیس بودن (برای پیش‌جمع‌آوری روزانه، جهت داشبورد سریع)، ولی هیچ‌جا خونده نمی‌شدن — نه کد مرده به معنای غیرقابل‌دسترس، بلکه یک ابزار عملیاتی معتبر که هیچ‌وقت زمان‌بندی نشده. تصمیم گرفته شد **این فاز اونو به داشبورد وصل نکنه**: `creator_studio_view` مستقیم از `PlayEvent`/`PointLedger` می‌خونه که در مقیاس MVP فعلی کاملاً کافیه و داده realtime‌تری هم می‌ده. وصل‌کردن اجباری `DailyTrackStat` بدون نیاز مقیاس واقعی، بهینه‌سازی زودهنگام بود (خلاف قانون «Scope Creep ممنوع»). یک تست پایه برای خود دستور `aggregate_stats` اضافه شد (قبلاً ۰٪ پوشش) چون کد قابل‌اجراست، ولی به هیچ view‌ای وصل نشد.

### ۹.۵ کد تغییرکرده
- `accounts/views.py::creator_studio_view` — دو باگ بالا رفع شد
- `explore/views.py::discover_view` — بخش `suggested_creators` جدید
- `templates/explore/discover.html` — رندر «افراد پیشنهادی»
- `explore/tests.py` — از خالی به ۱۶ تست (followed feed، Trending وزن‌دار، پیشنهاد Creator، پین‌ها، فیلتر نوع)
- `accounts/tests.py` — ۶ تست جدید برای `creator_studio_view` (شامل رگرسیون هر دو باگ)
- `plays/tests.py` — ۳ تست جدید برای `aggregate_stats`

### ۹.۶ تایید
- `python manage.py test` → **۳۴۳ تست** (از ۳۱۸)، همه pass
- `test core.tests_smoke`، `makemigrations --check`، `ruff check .`، `manage.py check` — تمیز
- تایید دستی در مرورگر واقعی: کاربری که یک Creator رو دنبال می‌کرد، ترک اون Creator رو زیر «تازه از افرادی که دنبال می‌کنی» دید؛ Trending فقط ترک با پخش واجد شرایط رو نشون داد؛ «افراد پیشنهادی» درست کسی که از قبل دنبال شده بود رو حذف کرد؛ داشبورد Creator بدون خطا شنونده جدید/برگشتی و عملکرد ترک رو نشون داد

### ۹.۷ معیار Done — همه برآورده شد
۱. ✅ کاربر لاگین‌کرده جدیدترین‌های Creatorهای دنبال‌شده رو بالای صفحه اصلی می‌بینه
۲. ✅ Trending فقط بر اساس پخش‌های واقعاً معتبر (Qualified Play) مرتب می‌شه، نه هر رویداد خام
۳. ✅ کاربر جدید/بدون‌Follow هم یک مسیر کشف Creator داره (Suggested Creators)
۴. ✅ داشبورد Creator شنونده اول‌بار/برگشتی و عملکرد هر ترک رو نشون می‌ده، بدون خطای Postgres
۵. ✅ هیچ query بدون `LIMIT` واقعی در سطح دیتابیس روی مسیرهای پرترافیک باقی نمونده

---

## بخش ۱۰ — فاز نهایی: Production، مونتیزیشن واقعی، تجربه رقابتی — ✅ تحویل شد (۲۰۲۶-۰۸-۲۰)

### ۱۰.۱ چرا این فاز
آخرین قدم قبل از رقابت واقعی با شنوتو/کست‌باکس/طاقچه. سه دسته به ترتیب اولویت کاربر: (A) سخت‌سازی
Production که بدونش deploy واقعی ممکن نیست، (B) تکمیل مونتیزیشن واقعی (نه dev-only)، (C) تجربه رقابتی.
حین کار، کاربر دو مورد اضافه هم خواست: SMS واقعی (item صفر) و پنل‌های داشبوردی حرفه‌ای‌تر برای درآمد/امتیاز
Creator و آمار پلتفرم برای staff.

### ۱۰.۲ کد جدید — خلاصه بر اساس دسته
**دسته ۰ (SMS):** `accounts/services.py` (provider abstraction: Console/Kavenegar).

**دسته A (Production):**
- `django-storages`+`boto3` — `USE_S3_STORAGE` در `prod.py`، S3-compatible عمومی (نه قفل روی یک provider)
- `config/celery.py` + `notifications/tasks.py` — فن‌اوت اعلان از سینک به Celery (eager در dev/test)
- Sentry (اختیاری، فقط با `SENTRY_DSN`)
- `core/views.py::health_check` (`/healthz/`) + `core/management/commands/backup_db.py` + `.casset/ops/backup.md`
- رفع باگ routing: `core/staff_urls.py` هیچ‌وقت mount نشده بود (مورد #۱۵)

**دسته B (مونتیزیشن):**
- `billing/services.py` — provider abstraction پرداخت (Zarinpal واقعی/Dev)، `start_payment`/`payment_callback`
- `billing/staff_views.py`/`staff_urls.py` — صف تایید payout
- رفع باگ: `create_payout_request` امتیاز رو کم نمی‌کرد (مورد #۱۷) — حالا از طریق PointLedger

**دسته C (تجربه رقابتی):**
- `explore/services.py` — SearchVector/SearchRank روی Postgres، icontains فالبک روی SQLite
- OG/meta tags (`base.html` + `track_detail.html` + `public_profile_pro.html`)
- `core/templatetags/thumbnails.py` — lazy thumbnail، بدون migration جدید
- Waveform تزئینی (CSS، نه peaks واقعی — تصمیم صریح، ffmpeg/pydub توجیه نداشت)
- داشبورد درآمد/امتیاز Creator (`creator_studio.html` — تراکنش‌های PointLedger + سوابق payout)
- داشبورد آماری پلتفرم برای staff (`core/staff_views.py::platform_dashboard`)
- بازبینی UX: `my_tracks.html` (برچسب فارسی + بج رنگی)، `upload.html` (بازخورد حین آپلود)

### ۱۰.۳ باگ‌های واقعی کشف‌شده (نه فرضی)
۱. **`core/staff_urls.py` هیچ‌وقت mount نشده بود** — کل پنل staff (users/creators console) از روز اول
   غیرقابل‌دسترس بود، هیچ‌کس (نه کاربر، نه Claude قبلی) متوجه نشده بود چون هیچ تستی هم روش نبود.
۲. **`core/staff_views.py::users_console` — `Sum(BooleanField)` روی Postgres** — همون کلاس باگ #۱۳ قبلی،
   ولی در یک view دیگه. چون این view تا همین فاز mount نشده بود، هیچ‌وقت این مسیر واقعاً اجرا نشده بود.
   **کشف‌شده توسط تایید زنده روی PostgreSQL واقعی** (همون روش pgserver فاز #۴) — دقیقاً همون ارزشی که آن
   فرآیند قبلاً هم ثابت کرده بود، این‌بار دوباره.
۳. **`create_payout_request` امتیاز کاربر رو کم نمی‌کرد** — بعد از تایید یک payout، همون امتیاز باز قابل
   درخواست مجدد بود. رفع شد با `PointLedger` deduction واقعی.
۴. **`ProfileSettingsForm` بدون اعتبارسنجی آپلود avatar/cover** — برخلاف Track/Album، هیچ چک MIME/سایزی
   نداشت.
۵. **`templates/accounts/public_profile.html` قالب orphan** — هیچ view‌ای رندرش نمی‌کرد؛ حذف شد.
۶. **OTP در production واقعاً SMS نمی‌فرستاد** — فقط یک پیام موفقیت نشون می‌داد.

### ۱۰.۴ تایید
- `python manage.py test` → **۴۱۳ تست** (از ۳۵۱)، همه pass روی SQLite
- **تایید زنده کامل روی PostgreSQL واقعی** (۱۶.۲، `pgserver` یکبارمصرف): `migrate` زیر `dev`/`prod` + کل
  ۴۱۳ تست، بعد از رفع باگ #۲ بالا — همه pass
- `makemigrations --check`, `ruff check .`, `manage.py check --deploy` (با env کامل prod) — تمیز
- تایید دستی کامل در مرورگر: خرید VIP end-to-end، صف payout staff، هر دو داشبورد جدید، پنل کاربران staff،
  بج‌های وضعیت فارسی، بازخورد آپلود، OG tags واقعی، waveform در playerbar

### ۱۰.۵ معیار Done — همه برآورده شد
۱. ✅ Production بدون S3/Zarinpal/Kavenegar credential واقعی fail-fast می‌کنه (نه silent broken deploy)
۲. ✅ خرید VIP از انتخاب پلن تا فعال‌شدن، از طریق یک درگاه پرداخت واقعی (نه فقط dev flag)
۳. ✅ تایید payout واقعاً امتیاز کم می‌کنه، دوباره قابل درخواست نیست
۴. ✅ جستجو روی Postgres واقعاً rank می‌کنه، نه فقط substring match
۵. ✅ لینک ترک/پروفایل در تلگرام/واتساپ/توییتر پیش‌نمایش درست نشون می‌ده
۶. ✅ Creator شفاف می‌بینه امتیازش از کجا اومده و کجا رفته؛ staff یک نمای کلی از سلامت پلتفرم داره
۷. ✅ صفحه انتظار بررسی و فرم آپلود دیگه بی‌بازخورد نیستن

---

## بخش ۱۱ — فاز حرفه‌ای: پلیر/پروفایل/آپلود/ادمین بازبینی جامع — ✅ تحویل شد (۲۰۲۶-۰۸-۲۰)

### ۱۱.۱ چرا این فاز
درخواست صریح صاحب پروژه: یک بازبینی end-to-end تا سطح حرفه‌ای، با تست مرورگری واقعی روی ۳ نوع اکانت
(شنونده عادی، Creator، VIP)، تمرکز روی پلیر، پروفایل، مدیریت محتوای خودسرویس، آپلود، و داشبورد ادمین
گرافیکی. یک تصمیم محصولی صریح از کاربر گرفته شد: لاگین اجباری برای پخش رد شد (تناقض با Embed/RSS)،
به‌جاش فقط سخت‌سازی امنیتی غیرمخرب انجام شد.

### ۱۱.۲ کد جدید — خلاصه بر اساس فاز
**فاز A (پلیر):** volume/mute، اسکرابر native همیشه‌نمایان، skip ±۱۰s، keyboard shortcuts، queue reorder،
نمای Now Playing تمام‌صفحه (`#npView`). رفع باگ `data-cover` (نیمی HTML خام/نیمی URL خام — یکسان‌سازی).

**فاز B (امنیت پخش):** `TRUST_PROXY_HEADERS` برای X-Forwarded-For (env-gated)، `PlayEvent` uniqueness
شامل `user` (migration `plays/0003`).

**فاز C (پروفایل):** رفع باگ لایک/صف مرده، اشتراک‌گذاری، لینک‌های اجتماعی، تب‌بندی واقعی، مودال
فالوور/فالووینگ (`api_user_connections`)، خودسرویس Unpublish (`toggle_track_visibility`)، Playlist
rename/reorder (migration `playlists/0002`)، رفع باگ دسترسی `playlist_detail` (owner-only بود).

**فاز D (آپلود):** `static/upload.js` — drag&drop، اعتبارسنجی کلاینت، تشخیص خودکار مدت‌زمان، پیش‌نمایش
کاور، progress bar واقعی با XHR.

**فاز E (ادمین):** `static/vendor/chart.umd.min.js` (Chart.js وندور محلی) — ۴ نمودار روند در
platform_dashboard + نمودار در creator_detail (بازطراحی کامل، تم تیره). Pagination روی همه‌ی صف‌های
staff. تاریخچه‌ی payout جدید.

**فاز F (تصویر):** thumbnail واقعی + gradient placeholder در ۵ تمپلیت که قبلاً کاور نشون نمی‌دادن.

### ۱۱.۳ باگ‌های واقعی کشف‌شده (نه فرضی)
۱. **`data-cover` دو قرارداد ناسازگار** — نیمی تمپلیت HTML خام، نیمی URL خام؛ `app.js` این رو `innerHTML`
   می‌کرد → کاور پلیربار از discover به‌صورت متن خام URL نشون داده می‌شد.
۲. **پروفایل: دکمه‌ی ♥ بدون `data-track`** — silent no-op.
۳. **پروفایل: دکمه‌ی ＋صف بدون data-src/title/by و بدون هیچ click handler در کل پروژه** — کاملاً نمادین.
۴. **`playlist_detail` فقط owner-only** — پلی‌لیست عمومی که از تب پروفایل جدید بهش لینک داده شد، برای
   همه‌ی کاربران دیگه ۴۰۴ می‌داد.
۵. **`get_client_ip` فقط REMOTE_ADDR** — پشت CDN همه یک IP می‌شدن؛ `PlayEvent` uniqueness بدون `user` —
   دو کاربر پشت یک IP فقط یک PlayEvent می‌گرفتن.
۶. **`t.publish_at` فیلد نامعتبر** در `creator_detail.html` (فیلد واقعی `published_at`).

### ۱۱.۴ تایید
- `python manage.py test` → **۵۰۲ تست** (از ۴۱۳)، همه pass روی SQLite
- **تایید زنده کامل روی PostgreSQL واقعی** (`scripts/local_postgres.py test`): **۵۰۳ تست**، همه pass —
  بدون باگ کلاس `Sum(boolean)` جدید، دو migration جدید (`plays/0003`, `playlists/0002`) بدون خطا اعمال شدن
- `ruff check .` (۱۱ خطا پیدا و رفع شد)، `makemigrations --check`، `manage.py check --deploy` — تمیز
- تایید دستی end-to-end در مرورگر با ۳ اکانت واقعی (`demo_4` شنونده، `demo_1` Creator، `demo_2` VIP):
  پلیر (تست مستقیم DOM/JS برای هر کنترل)، پروفایل، پلی‌لیست، آپلود (submit واقعی تا redirect)، دانلود
  VIP-gated، داشبورد ادمین گرافیکی

### ۱۱.۵ معیار Done — همه برآورده شد
۱. ✅ پلیر: volume، seek قابل‌لمس همه‌جا (حتی موبایل)، skip، keyboard، queue reorder، Now Playing
۲. ✅ هیچ دکمه‌ی نمادین/مرده‌ای در پروفایل، آپلود، یا صفحه‌ی ترک باقی نمونده (تایید با ۳ اکانت واقعی)
۳. ✅ Creator می‌تونه بدون تماس با staff، محتوای منتشرشده رو خودش مخفی/دوباره منتشر کنه
۴. ✅ داشبورد ادمین گرافیکیه، نه فقط عدد خام؛ همه‌ی صف‌ها pagination دارن
۵. ✅ لاگین اجباری برای پخش عمداً اضافه نشد (تصمیم صریح کاربر) — فقط سخت‌سازی IP/dedup
