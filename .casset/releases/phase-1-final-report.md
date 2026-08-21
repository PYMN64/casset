# Casset — گزارش نهایی فاز ۱ (COMPLETE)

> این سند مرجع رسمی «فاز ۱ تمام شد» است — هم‌تراز با صفحهٔ Notion «۱۰ — گزارش
> نهایی فاز ۱». از اینجا به بعد مرجع کار **فاز ۲** است:
> `.casset/releases/v2.1.0-phase2-plan.md`. فاز ۱ از نگارش اول (۷ اوت ۲۰۲۶) تا
> تگ `v2.0.0` (۲۱ اوت ۲۰۲۶) طول کشید.

## نتیجهٔ نهایی فاز ۱

- **۵۹۱ تست خودکار سبز** (SQLite و PostgreSQL ۱۶ واقعی) — از صفر تست در شروع کار.
- **پوشش تست: ۹۲٪** (اندازه‌گیری ۲۰۲۶-۰۸-۲۱، جایگزین عدد قدیمی ۸۱٪).
- `ruff check .` تمیز؛ `manage.py check --deploy` زیر تنظیمات prod تمیز.
- Baseline گیت: تگ `v2.0.0`.
- ۴۴ باگ/بدهی فنی واقعی شناسایی و رفع شد (فهرست کامل در بخش پایین).
- ممیزی پایانی ۲۰۲۶-۰۸-۲۱: صفر کد نمادین/stub، صفر برنچ conflict‌دار، تنها
  مشکل واقعی آلودگی line-ending (CRLF) بود که رفع شد. جزئیات کامل:
  `.casset/state/audit-2026-08-21.md`.

## مسیر Sprint-به-Sprint

| Sprint | موضوع | وضعیت |
|---|---|---|
| S0 | Foundation — Brain، dependency، env، اولین تست‌ها، PostgreSQL | ✅ |
| S1 | Identity — ثبت‌نام، OTP، پروفایل، آنبوردینگ Creator | ✅ |
| S2 | Content — آپلود، اعتبارسنجی، متادیتا، چرخهٔ publish | ✅ |
| S3 | Moderation — صف بررسی، تایید/رد، گزارش، audit trail | ✅ |
| S4 | Playback Core — PlaybackSession/Event، qualification سمت سرور | ✅ |
| S5 | Play Intelligence — ضدتقلب پایه، QualifiedPlay، PointLedger | ✅ |
| S6 | Analytics — آمار ترک/سازنده، داشبورد | ✅ |
| S7 | Discovery — جستجو، Explore، Trending، پروفایل عمومی | ✅ |
| S8 | Production — Postgres، Redis، Celery، Object Storage، امنیت، بک‌آپ، استقرار | ✅ |

## نسخه‌های منتشرشده در طول فاز ۱

1. **v1.0** (MVP baseline) — ۴۱۷ تست، Postgres تأیید‌شده زنده، Zarinpal/Kavenegar واقعی.
2. **v1.2.0** ("v1 professional") — پلیر حرفه‌ای کامل (volume/scrubber/shortcuts/queue)، پروفایل بازسازی‌شده، آپلود drag&drop، داشبورد ادمین گرافیکی. ۵۰۳ تست.
3. **v2.0.0** ("Orange Noir v2"، تگ فعلی) — بازطراحی کامل فرانت‌اند، ورود گوگل (OIDC بومی)، قانون انتشاردهنده، تنظیمات اعلان، سئو/PWA. ۵۹۱ تست.
4. **ممیزی پایانی ۲۰۲۶-۰۸-۲۱** — بررسی کامل کد/گیت/مستندات پیش از فاز ۲؛ صفر کد نمادین یا برنچ معیوب پیدا شد؛ تنها مشکل واقعی آلودگی CRLF بود (رفع شد)؛ پوشش تست ۸۱٪→۹۲٪ به‌روزرسانی شد.

## فهرست کامل ۴۴ باگ/بدهی فنی واقعی رفع‌شده

۱. کرش `AlbumForm`/`Album` (فیلد `kind` نامرتبط) — رفع با اصلاح فرم + اعتبارسنجی کاور.
۲. دو مدل `Plan` موازی و ناسازگار (`billing` vs `subscriptions`) — `subscriptions` به `_deprecated/` منتقل شد.
۳. امتیاز مستقیم روی `UserProfile.points` — `PointLedger` ساخته شد.
۴. SQLite در production بدون تنظیمات Postgres — `DB_ENGINE` هاردن شد، اتصال زندهٔ Postgres ۱۶.۲ کامل تأیید شد.
۵. `pyproject.toml` ناهماهنگ با پکیج‌های واقعی — بازنویسی کامل.
۶. پوشش تست صفر — از صفر به ۵۹۱ تست.
۷. بدون سیستم Notification/Activity Feed — اپ `notifications` با ۹ verb ساخته شد.
۸. `SECRET_KEY`/`PLAY_IP_SALT`/`PLAY_UA_SALT` fallback ناامن — fail-fast در prod.
۹. `interactions/urls.py` فقط ۲ endpoint داشت — به ۶ endpoint کامل رسید (کامنت، لایک، فالو، بلاک، Favorite، Repost).
۱۰. پلیر بدون سرعت/Resume/Sleep Timer — همه اضافه شدند.
۱۱. Staff بدون اکشن روی Report، بدون تعلیق حساب — هر دو ساخته شد.
۱۲. اعلان نقطه‌عطف پخش (کد مرده) — واقعاً وصل شد.
۱۳. `Sum(BooleanField)` روی PostgreSQL کرش می‌کرد (`creator_studio_view`) — با `Count(filter=Q(...))` رفع شد؛ در حین ممیزی کد قبل از نوشتن کد کشف شد.
۱۴. کوئری بدون `LIMIT` در سطح SQL (`list(qs)[:50]`) — به `list(qs[:50])` اصلاح شد.
۱۵. پنل staff (`core/staff_urls.py`) هیچ‌وقت `include()` نشده بود — مونت شد.
۱۶. همان باگ #۱۳ در `users_console` — با اجرای زندهٔ Postgres کشف و رفع شد.
۱۷. `create_payout_request` امتیاز کاربر را کم نمی‌کرد — کسر واقعی از طریق `PointLedger`.
۱۸. آپلود avatar/cover پروفایل بدون اعتبارسنجی MIME/سایز — validator مشترک اضافه شد.
۱۹. قالب یتیم `public_profile.html` — حذف شد.
۲۰. OTP در production واقعاً SMS نمی‌فرستاد — provider واقعی Kavenegar اضافه شد.
۲۱. باگ بحرانی: روت `slug` استاندارد جنگو Unicode فارسی را نمی‌پذیرفت — `UnicodeSlugConverter` ساخته شد؛ صفحهٔ هر ترک با عنوان فارسی کاملاً غیرقابل‌دسترس بود.
۲۲. `config/settings/__init__.py` بی‌صدا به `dev.py` fallback می‌کرد — `ImportError` صریح.
۲۳. OG image با ساخت دستی URL خراب می‌شد روی S3 — `abs_url` templatetag اضافه شد.
۲۴. ۳ قالب یتیم دیگر (`creator_dashboard.html`, `playlists/index.html`, `artist_profile.html`) — حذف شدند.
۲۵. ۴ مدل کلیدی در ادمین ثبت نشده بودند — همه ثبت شدند؛ `AuditLog` عمداً read-only.
۲۶. مودال «افزودن به پلی‌لیست» و پنل صف پخش در JS پیاده‌سازی شده بودند ولی هیچ‌جای HTML وجود نداشتند (silent no-op) — overlay panelهای واقعی اضافه شدند.
۲۷. `library_view` بدون `annotate(item_count=...)` — رفع شد؛ نام پلی‌لیست هم با context key اشتباه رندر نمی‌شد.
۲۸. `can_download` context ست نمی‌شد — دکمهٔ دانلود VIP هیچ‌وقت دیده نمی‌شد.
۲۹. نیمی از قالب‌ها `data-cover` را HTML خام می‌ساختند، نیمی فقط URL — قرارداد یکسان شد (فقط URL خام)، امنیت هم بهتر شد (تزریق HTML حذف شد).
۳۰. دکمهٔ لایک پروفایل بدون `data-track`، دکمهٔ افزودن به صف بدون click handler — هر دو رفع شدند.
۳۱. `playlist_detail` فقط برای owner کار می‌کرد — پلی‌لیست عمومی برای همه قابل‌دیدن شد.
۳۲. `get_client_ip` فقط `REMOTE_ADDR` می‌خواند (بی‌اثر پشت CDN) — `TRUST_PROXY_HEADERS` اضافه شد؛ `PlayEvent` uniqueness شامل `user` شد.
۳۳. پلیر global بدون volume/seek قابل‌لمس/skip/shortcut/reorder صف — همه در فاز حرفه‌ای اضافه شدند.
۳۴. `staff/creator_detail.html` به فیلد ناموجود `t.publish_at` ارجاع می‌داد — به `published_at` اصلاح شد.
۳۵. باگ بحرانی خاموش: CSP خودِ پروژه Google Fonts را بلاک می‌کرد — فونت Vazirmatn هرگز لود نمی‌شد؛ self-host شد، CSP سخت‌تر شد.
۳۶. XSS ذخیره‌شده در JSON-LD (`json.dumps` کاراکتر `<` را escape نمی‌کرد) — رفع شد.
۳۷. کامنت چندخطی جنگو (`{# #}`) روی صفحات به‌عنوان متن چاپ می‌شد — به `{% comment %}` تبدیل شد.
۳۸. اسکرول افقی روی موبایل در همهٔ صفحات (سه علت مستقل) — همه رفع شدند.
۳۹. تم روشن WCAG AA را رد می‌کرد (کمترین کنتراست ۲.۳۵:۱) — به ۵.۰۲:۱ رسید.
۴۰. مودال تایید هندلر AJAX را دور می‌زد (`form.submit()`) — به `requestSubmit()` تغییر کرد.
۴۱. درگ‌اند‌دراپ پلی‌لیست فقط جابه‌جایی تک‌پله‌ای می‌فهمید — پذیرش آرایهٔ کامل با چک مالکیت.
۴۲. opt-out اعلان از یک reverse-OneToOne کش‌شده خوانده می‌شد و نادیده گرفته می‌شد — کوئری مستقیم شد.
۴۳. فایل‌های استاتیک هش‌نشده + service worker cache-first — دیپلوی به کاربر نمی‌رسید؛ `ManifestStaticFilesStorage` اضافه شد.
۴۴. ورود با گوگل فقط placeholder بود — OIDC بومی کامل با PKCE/state/nonce ساخته شد.

## اصول رعایت‌شده در طول فاز ۱

- **بدون بازنویسی.** هیچ‌کدام از ۴۴ مورد بالا با rewrite حل نشد؛ همه افزایشی روی کد موجود.
- **هر فیچر مهم با تست.** از صفر به ۵۹۱ تست.
- **PointLedger تنها منبع حقیقت امتیاز.** `UserProfile.points` هرگز مستقیم دستکاری نشد.
- **Qualified Play فقط سمت سرور.** client progress هرگز به‌تنهایی proof نبود.

## آنچه به‌عمد فاز ۱ نشد (منتقل‌شده به فاز ۲)

تأیید ایمیل ثبت‌نام با رمز، اتصال بانکی واقعی تسویه، rate limit روی ثبت‌نام/لاگین،
بک‌آپ خودکار زمان‌بندی‌شده، اتصال `DailyTrackStat` به داشبوردها. جزئیات کامل و
اولویت‌بندی: `.casset/releases/v2.1.0-phase2-plan.md`.

---

**فاز ۱ اینجا رسماً بسته اعلام می‌شود.** ادامهٔ کار از صفحهٔ «۱۱ — نقشهٔ فاز ۲»
(Notion) و `.casset/releases/v2.1.0-phase2-plan.md` (ریپازیتوری) است.
