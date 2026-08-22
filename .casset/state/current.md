# Casset Current State

> **۲۰۲۶-۰۸-۲۲ — پس از S12: یک پاس بزرگ رفع‌باگ/UX سراسری بسته شد.** طبق
> قانون طلایی `CLAUDE.md` بخش ۵، این بلوک بعد از هر تسک/اسپرینت جایگزین
> می‌شود (نه اضافه، جایگزینی کامل):
>
> **آخرین تسک تمام‌شده:** یک تسک ad-hoc (خارج از شماره‌گذاری S10-S13 نقشه‌ی
> فاز ۲؛ درخواست مستقیم PYMN) که ~۱۹ باگ/درخواست UX واقعی را در پلیر،
> پلی‌لیست، اعلان‌ها، لایک/فالو، کارت‌های Discover، تنظیمات حساب و صفحه‌ی
> پروفایل رفع کرد:
> - **ثبت‌نام:** فیلد یوزرنیم از فرم ثبت‌نام رمزی حذف شد (مثل مسیر
>   پیامک/گوگل auto-generate می‌شود) — یوزرنیم عمومی فقط یک‌بار، در گیت
>   انتشاردهنده انتخاب می‌شود. ورود حالا با ایمیل *یا* یوزرنیم کار می‌کند
>   (`accounts/backends.py::EmailOrUsernameBackend` جدید).
> - **پلیر:** دکمه‌ی بستن واقعی (`#pbClose`) اضافه شد؛ باگ `qClose`/`plClose`/
>   `embedClose` که با کلیک روی آیکون داخلی کار نمی‌کرد رفع شد (`.closest()`
>   به‌جای `e.target.id`)؛ باگ Repeat که آیکون را با ایموجی جایگزین و برای
>   همیشه نابود می‌کرد رفع شد؛ Shuffle بررسی و تایید شد که درست کار می‌کند؛
>   دکمه‌ی + (افزودن به پلی‌لیست) که کلا wire نشده بود الان کار می‌کند؛
>   آیکون‌های نوار پخش کوچک‌تر و واکنش‌گرا شدند.
> - **پلی‌لیست:** مودال «افزودن به پلی‌لیست» حالا فرم ساخت سریع inline دارد
>   و آیکون هر پلی‌لیست وضعیت واقعی عضویت را نشان می‌دهد (endpoint
>   `api_playlist_mine` یک پارامتر `track_id` جدید گرفت). Toast بالای مودال
>   نمایش داده می‌شود (z-index اصلاح شد).
> - **لایک/فالو:** حالت لایک (پر/توخالی) و تعداد لایک حالا روی کارت‌های
>   Discover/Trending هم درست است (endpoint جدید `api_likes_status` +
>   hydration سبک سمت کلاینت). دکمه‌ی فالو بعد از کلیک متن و رنگش عوض
>   می‌شود («دنبال کردن» ↔ «لغو دنبال کردن»؛ context جدید `is_following`).
> - **منوی «⋯»:** باگ z-index که منو را زیر کارت بعدی می‌برد (تله‌ی
>   stacking-context ناشی از backdrop-filter در `.card`) با یک fix سراسری
>   در `casset-ui.js::initMenus` (پورتال به `<body>`) حل شد — همه‌ی صفحات.
> - **اعلان‌ها:** دراپ‌داون واقعی زیر زنگوله (به‌جای لینک مستقیم به صفحه‌ی
>   کامل) با پیش‌نمایش آخرین اعلان‌ها.
> - **Discover:** کارت‌های مربعی به طرح «نوار کاست» بازطراحی شدند (بدون از
>   دست رفتن هیچ گزینه/آیکونی).
> - **تنظیمات حساب:** عرض فیلدها محدود شد (۶۴۰px به‌جای کل ستون محتوا)،
>   ویجت آواتار/کاور دیگر URL خام مدیا را نشان نمی‌دهد (`ClearableFileInput`
>   → `FileInput`)، و باکس پیش‌نمایش خودش دکمه‌ی آپلود شد (کلیک = انتخاب فایل).
> - **صفحه‌ی پروفایل:** نوشته‌ها/دکمه‌های روی کاور (لینک‌های اجتماعی، دنبال
>   کردن/اشتراک/گزارش) به زیر کاور منتقل شدند؛ فقط نام/هندل/بیو کنار آواتار
>   روی خود تصویر می‌مانند.
> - **باز مانده — نیاز به ورودی PYMN:** یک فلش جهت‌دار روی صفحه‌ی پروفایل
>   («روبروی متن آثار، سمت چپ») که هنوز پیدا نشده — تمام آیکون‌های ▲▼ سایت
>   بررسی شدند، تنها نامزد قابل‌مشاهده روی همه‌ی صفحات caret منوی حساب در
>   نوار بالاست که با توضیح کاربر کاملاً جور درنمی‌آمد؛ PYMN عکس/توضیح دقیق‌تر
>   می‌فرستد.
> **فایل‌های تغییریافته:** `accounts/{forms,views,tests,tests_email_verification,tests_rate_limit}.py`,
> `accounts/backends.py` (جدید), `config/settings/base.py`,
> `interactions/{views,urls,tests}.py`, `playlists/{views,tests}.py`,
> `tracks/{views,tests}.py`, `scripts/qa/journey_qa.py`,
> `static/{app.css,app.js}`, `static/css/casset-ui.css`, `static/js/casset-ui.js`,
> `templates/base.html`, `templates/accounts/{login,register,settings,public_profile_pro}.html`,
> `templates/tracks/track_detail.html`, `templates/partials/_tcard.html`.
> **تست:** ۷۰۸ تست سبز روی SQLite (از ۶۹۴، +۱۴)، **۷۰۹ روی PostgreSQL واقعی
> محلی** (همان ۵ شکست پیش‌موجود و نامرتبط `core.tests_settings_secrets` —
> مشکل Winsock محلی ویندوز، هم روی SQLite هم Postgres، هم قبل از این تسک هم
> بعدش)، `ruff check .` تمیز، بدون migration drift،
> `python manage.py makemigrations --check` تمیز. `scripts/qa/journey_qa.py`
> («۶۰ ادعای مسیر واقعی») هم به‌روزرسانی شد (مسیر ثبت‌نام آن هنوز فرض می‌کرد
> ثبت‌نام مستقیم به onboarding ریدایرکت می‌شود — یک فرض قدیمی از قبل S10 که
> هیچ‌وقت با گیت تایید ایمیل sync نشده بود؛ الان مسیر واقعی
> ثبت‌نام→تاییدایمیل→onboarding را طی می‌کند) — **۶۴ از ۶۴ ادعا سبز**.
> تایید دستی end-to-end در مرورگر برای هر آیتم بالا (پلیر/پلی‌لیست/لایک/
> فالو/منو/اعلان/کارت‌ها/تنظیمات/پروفایل) با DOM assertions مستقیم (screenshot
> در این محیط sandbox در دسترس نبود — pane نمایش داده نمی‌شد).
> **وضعیت commit:** ✅ pushed. کامیت `5034022` (شامل S12 قبلی + این تسک) از
> `feature/s12-analytics-personalization` با fast-forward به `master` merge و
> به `origin/master` push شد — طبق دستور صریح PYMN در همین تسک. هش محلی و
> ریموت با `git ls-remote` تایید شدند (یکی هستند).
> **قدم بعدی پیشنهادی:** ۱) فلش گمشده روی پروفایل با عکس/توضیح دقیق‌تر PYMN
> رفع شود. ۲) S13 — اتصال بانکی واقعی تسویه؛ منتظر قرارداد بانکی PYMN.
> **نکات باز:** فلش پروفایل (بالا). Notion به‌روزرسانی نشد — MCP آن در این
> session احراز هویت نشده؛ PYMN باید از تنظیمات کانکتور claude.ai یا
> `/mcp` وصلش کند.
>
> قبلی از این بلوک: `.casset/state/audit-2026-08-21.md` را بخوان، بعد
> `.casset/releases/v2.1.0-phase2-plan.md`.

## v2.0.0 — "Orange Noir v2 / MVP قابل انتشار" (2026-08-21) — CURRENT BASELINE

**این نقطهٔ مرجع همهٔ کارهای بعدی است.** تگ `v2.0.0`. قبل از شروع هر کار جدید
با `git log` / `git tag` مطمئن شو روی همین تگ یا جلوتر از آن هستی.

**سند کامل این فاز: `.casset/releases/v2.0.0-mvp.md`** — اول آن را بخوان.
خلاصهٔ تغییرات معماری: `.casset/state/changelog.md` (entry بالای فایل).

بازطراحی کامل فرانت‌اند روی همان Django templates (بدون بازنویسی، بدون بیلد
فرانت جدا) به‌علاوهٔ سه فیچر بک‌اندی که برای انتشار عمومی لازم بودند.

- **۵۹۱ تست سبز** روی SQLite و روی PostgreSQL ۱۶ واقعی (از ۵۰۲/۵۰۳).
  `ruff check .` تمیز. `check --deploy` زیر تنظیمات prod تمیز.
- **ورود با گوگل** — پیاده‌سازی بومی OIDC با PKCE، state و nonce؛ بدون
  وابستگی جدید. allauth عمداً استفاده نشد (دلیل در سند release).
- **قانون انتشاردهنده** — `UserProfile.can_publish` = یوزرنیم عمومی + شمارهٔ
  موبایل تاییدشده. گیت روی «ارسال برای بررسی» است، نه روی آپلود پیش‌نویس.
  فیچر جدید: تایید شماره برای حساب واردشده (`/account/phone/`).
- **تنظیمات اعلان** — `NotificationPreference` با یک نقطهٔ اعمال؛ خاموش‌کردن
  واقعاً جلوی نوشتن ردیف را می‌گیرد. نتایج بررسی (تایید/رد) قابل ساکت‌کردن
  نیستند.
- **سیستم طراحی Orange Noir v2** — توکن کامل، تم روشن واقعی و مستقل، لایهٔ
  کامپوننت جدا، هویت پلیر «کاست» (قرقره، برچسب کاغذی، اسکرابر نواری).
  `style=` در قالب‌ها از ۴۰۵ به ۱ رسید. آیکون از ۲۴ به ۸۱ نماد.
- **سئو و PWA** — sitemap، robots تولیدشده، JSON-LD به‌ازای نوع محتوا، عنوان
  یکتای زیر ۶۰ کاراکتر، ست آیکون کامل، service worker با استراتژی به‌ازای
  نوع منبع.

### باگ‌های واقعیِ منتشرشده که در این نسخه رفع شدند

اینها در نسخهٔ زنده وجود داشتند و در بازبینی چشمی دیده نمی‌شدند:

1. **فونت Vazirmatn هرگز لود نمی‌شد** — CSP خود پروژه Google Fonts را بلاک
   می‌کرد. فونت self-host شد و CSP سخت‌تر شد.
2. **XSS ذخیره‌شده در JSON-LD** — `json.dumps` کاراکتر `<` را escape نمی‌کند.
3. **کامنت چندخطی `{# #}` روی همهٔ صفحات به‌عنوان متن چاپ می‌شد.**
4. **اسکرول افقی روی موبایل در همهٔ صفحات** (سه علت مستقل).
5. **تم روشن WCAG AA را رد می‌کرد** (سفید روی دکمهٔ اصلی: ۲.۳۵:۱).
6. **مودال تایید هندلر AJAX را دور می‌زد** → کاربر روی JSON خام می‌افتاد.
7. **درگ‌اند‌دراپ پلی‌لیست** به endpointی پست می‌کرد که آن شکل را نمی‌پذیرفت.
8. **opt-out اعلان از یک attribute کش‌شده خوانده می‌شد** و نادیده گرفته می‌شد.
9. **فایل‌های استاتیک هش‌نشده + SW با cache-first** = دیپلوی به کاربر نمی‌رسید.

### ابزار QA که باقی می‌ماند

```powershell
python manage.py test                     # ۵۹۱ تست
python scripts/local_postgres.py test     # همان روی PostgreSQL واقعی
python scripts/qa/journey_qa.py           # ۶۰ ادعای مسیر واقعی روی DB زنده
# scripts/qa/responsive_qa.js             # در کنسول مرورگر: سرریز افقی
```

`journey_qa.py` دو باگ واقعی پیدا کرد که تست واحد نگرفته بود — قبل از هر
release اجرایش کن.

### آنچه عمداً انجام نشد

| مورد | چرا |
|---|---|
| واریز بانکی تسویه | نیاز به قرارداد بانکی — صفحه این را صریح می‌گوید |
| Vite / Alpine / htmx | ریسک عملیاتی بدون سود کاربری (بخش ۵.۱ سند release) |
| تایید ایمیل برای ثبت‌نام با رمز | تنها شکاف باقی‌ماندهٔ هویت — اولویت بعدی |
| اپ نیتیو | PWA نصب‌شدنی آماده است؛ Capacitor مسیر بعدی |

### قدم‌های بعدی پیشنهادی

۱. تایید ایمیل برای ثبت‌نام با رمز
۲. اتصال بانکی تسویه
۳. Rate limit روی ثبت‌نام و لاگین (الان فقط OTP و جستجو دارند)
۴. بک‌آپ خودکار زمان‌بندی‌شده
۵. اتصال `DailyTrackStat` به داشبوردها

---

## v1.2.0 — "v1 professional" (2026-08-20) — نسخهٔ قبلی

**نسخهٔ قبلی — مرجع فعلی v2.0.0 است (بالای همین فایل).** Tagged and pushed to
`origin/master` on GitHub (`https://github.com/PYMN64/casset.git`) as
annotated tag `v1.2.0`, commit `f396b3c`. Deployable with no separate
frontend build (Django templates + hand-written `static/app.js`/`app.css`,
no bundler). Before starting any new work, confirm the working tree is at or
ahead of this tag (`git log`, `git tag`) — do not build on an older commit.
Several stale local-only tags from earlier sessions (`v.2.0.0`, `v1.1.0`,
`v1.1.0-stabilization`, `v2`, `v2-safe`) exist on disk but were never pushed
and don't belong to this linear history — ignore them.

Second major pass on top of the v1.0 baseline below, triggered by an explicit
owner request for an end-to-end professional-grade review (player, profile,
upload, admin dashboard) with real browser QA across 3 account types
(listener, creator, VIP). Full detail: `.casset/state/changelog.md` entry
"فاز حرفه‌ای — پلیر/پروفایل/آپلود/ادمین بازبینی جامع".

- **503 tests green on real PostgreSQL** (502 on SQLite + 1 Postgres-only
  full-text-search test), up from 417/416. `ruff check .` clean.
- Player: volume/mute, always-visible native seek scrubber (touch + keyboard
  free), ±10s skip, full keyboard shortcuts, queue reorder, full-screen
  "Now Playing" view.
- Playback security hardened (without login-gating playback — explicit owner
  decision, since Embed/RSS podcast distribution require anonymous access):
  `TRUST_PROXY_HEADERS` for safe X-Forwarded-For behind a trusted proxy,
  `PlayEvent` uniqueness now includes `user` (was silently colliding for
  different users behind the same IP/NAT).
- Profile page rebuilt: two real dead-button bugs fixed (like, add-to-queue),
  share button, social links, real content tabs, follower/following modal,
  self-service unpublish, playlist rename/reorder (plus a real access-control
  bug fix — public playlists were 404ing for everyone but the owner).
- Upload flow rebuilt: drag & drop, real XHR progress, client-side
  validation, browser-side duration auto-detect, cover preview.
- Staff dashboard is now graphical: Chart.js vendored locally (no CDN), 4
  trend charts on the platform dashboard, a per-creator performance chart,
  and pagination added to every staff queue (previously unpaginated or
  hard-capped with no way to see more).
- Image polish: a real cover thumbnail (with a gradient placeholder
  fallback) now renders in 5 list templates that previously showed no
  artwork at all; a real bug in the `data-cover` convention (half the
  templates emitted raw HTML into an attribute the player treated as a
  plain URL) is fixed everywhere.

## v1.0 — MVP baseline (2026-08-20)

This tree is the **v1 reference point**: the first fully working, tested,
production-shaped version of Casset. Everything below describes how it got
here; `.casset/state/changelog.md` has the per-change detail.

- **417 tests green on real PostgreSQL** (416 on SQLite + 1 Postgres-only
  full-text-search test). `ruff check .` fully clean for the first time.
- Postgres is now permanent dev infrastructure, not a one-off verification:
  `python scripts/local_postgres.py test` runs the whole suite against a real
  server with no Docker/admin rights needed.
- Production hardening in place: S3-compatible object storage (opt-in),
  Celery+Redis, Sentry, `/healthz/`, `backup_db`, and fail-fast prod guards
  for DB / SMS / payment credentials.
- Monetization is real, not dev-only: Zarinpal provider abstraction and
  creator payouts that actually deduct points through `PointLedger`.
- Demo data: `python manage.py seed_demo --users 33` populates every
  dashboard and queue with realistic activity.

**Known blockers for an actual production deploy** (deliberate, not bugs):
real `ZARINPAL_MERCHANT_ID`, `KAVENEGAR_API_KEY`, and S3 credentials must be
supplied by the owner — prod refuses to boot without them, by design.

## Status
Phase 1 (Foundation Stabilization) **closed** 2026-08-19 — all 8 items in CLAUDE.md §3 resolved.
Phase 2 (revised — social endpoints + player UX, roadmap §7) **closed** 2026-08-19 — items #9/#10 resolved.
Phase 3 (Trust & Safety, roadmap §8) **closed** 2026-08-19 — items #11/#12 resolved (report actions,
account suspension, creator-side comment block, auto-approve toggle, milestone notification wired).
Phase 4+5 (merged — personal feed + creator analytics + smart discovery, roadmap §9) **closed**
2026-08-20 — items #13/#14 resolved. Follow-feed, qualified-play-weighted trending, and suggested
creators were found already sitting uncommitted from a parallel session; reviewed (2 real bugs found
and fixed, see §9.2), completed (suggested creators), and fully tested (0 → 25 tests across explore/
accounts/plays).
Final phase (Production hardening + real monetization + competitive UX, roadmap §10) **closed**
2026-08-20 — items #15-#20 resolved. Real SMS (Kavenegar) + payment gateway (Zarinpal) providers,
S3-compatible object storage, Celery, Sentry, health check, backup command, real payout point deduction,
Postgres full-text search, OG tags, thumbnail pipeline, creator earnings dashboard, staff platform
dashboard, decorative waveform, upload/review UX pass. Two real Sum(BooleanField)-on-PostgreSQL bugs
found this session (one via code audit before writing code, one via the live-Postgres verification pass
itself — same class as item #13, in a view that had never been reachable before this session fixed its
routing).
Professional pass (player/profile/upload/admin dashboard, roadmap phase "فاز حرفه‌ای") **closed**
2026-08-20 — items #29-#34 resolved. See the "v1.2.0" section above for the summary; full
detail in changelog.md. 502→503 tests, live-Postgres-verified, ruff clean, manually QA'd in-browser
across 3 real demo accounts (plain listener, creator, VIP). **Tagged `v1.2.0` and pushed to
`origin/master` on GitHub 2026-08-20 — this is the current baseline for all future work.**

## Repository strategy
Keep the existing Django modular monolith. Stabilize and refactor critical domains instead of rewriting.

## Current critical path
S0 Foundation ✅ → S1 Identity ✅ → S2 Content/Social ✅ → S3 Moderation ✅ → S4 Playback ✅ → S5 Play Intelligence ✅ → S6 Analytics ✅ → S7 Discovery ✅ → S8 Production ✅ → **S9 Real deploy (next — needs real S3/Zarinpal/Kavenegar credentials from PYMN)**.

## Current release criterion
The creator/listener business flow must work end-to-end and produce trustworthy qualified-play, analytics and reward records.

## Agent status
Agent system is designed but intentionally not activated as autonomous development infrastructure until Brain + test foundation are in place.

## Change log index
All architectural changes are recorded in `.casset/state/changelog.md`.
Read that file at the start of every session to know what has changed and why.

## Test coverage baseline (2026-08-22, post S12-UX-pass, current)
`coverage run --source=. manage.py test` → **93% overall**, 708 tests, `OK (skipped=1)`.
Up from 694/93% (post-S12) after the ad-hoc UX/bugfix pass (player controls,
playlist modal, like/follow state, the sitewide "⋯" menu z-index fix, notification
dropdown, discover card redesign, account settings, profile page) added 14 tests
with no coverage regression. Verified against a real local PostgreSQL server too
(709 tests, one more than SQLite for the Postgres-only full-text-search test) —
same 5 pre-existing unrelated failures (`core.tests_settings_secrets`, a local
Windows Winsock issue) on both databases, before and after this pass.
`scripts/qa/journey_qa.py` (60+ live-database assertions) also green — 64/64.
Full HTML report regeneratable with `coverage html` (not committed, `.gitignore`d).

### (superseded) 2026-08-22 post-S12 baseline
`coverage run --source=. manage.py test` → 93% overall, 694 tests, `OK (skipped=1)`.
Up from 660/92% (post-S11) after S12 (creator geo/device analytics breakdown +
lightweight Discover recommendation layer) added 34 tests with no coverage regression —
see `.casset/execution/logs/s12-log.md`. Verified against a real local PostgreSQL
server (695 tests, one more than SQLite for the Postgres-only full-text-search test).

### (superseded) 2026-08-22 post-S11 baseline
`coverage run --source=. manage.py test` → 92% overall, 660 tests, `OK (skipped=1)`.
Up from 645/92% (post-S10) after S11 (PlaybackSession, play-event fraud signals, AuditLog
ORM-level immutability, DailyTrackStat wired into the creator studio dashboard) added 15 tests
with no coverage regression — see `.casset/execution/logs/s11-log.md`.

### (superseded) 2026-08-21 post-S10 baseline
`coverage run --source=. manage.py test` → 92% overall, 629 tests, `OK (skipped=1)`.
Up from 591/92% (pre-Phase-2 audit baseline) after S10 (email verification, login/register
rate limiting, settings fail-fast confirmation, scheduled backup, CI) added 37 tests with no
coverage regression — see `.casset/execution/logs/s10-log.md`.

### (superseded) 2026-08-21 pre-S10 baseline
`coverage run --source=. manage.py test` → 92% overall, 591 tests, `OK (skipped=1)`.
Re-measured 2026-08-21 as part of the pre-Phase-2 audit (see `.casset/state/audit-2026-08-21.md`);
supersedes the stale 81%/242-test number below, which predated Phase 2 through the professional pass.

### (superseded) 2026-08-19 baseline
`coverage run --source=. manage.py test` → 81% overall (242 tests, 2640 statements, 494 missed).
Kept only for history — see the current number above.

Notably low as of the 242-test baseline (real gaps, not noise):
- `interactions/views.py` — 22% (likes/follows/comments — the social layer the product identity depends on; now covered by 34 tests, see changelog 2026-08-19 "فاز ۲ بازنگری‌شده تحویل شد")
- `playlists/views.py` — 45%
- `notifications/signals.py` — 69% (the wiring itself; `notifications/services.py` is 100%)
- `explore/views.py` — 70%
- `core/staff_views.py` / `core/staff_urls.py` — 0% (untested internal staff surface)
- management commands (`aggregate_stats`, `recalculate_points`, `seed_genres`) — 0%

`config/asgi.py`/`wsgi.py`/`settings/prod.py` at 0% is expected (deploy entry points, not exercised by the dev-settings test run) — not a real gap.

## Test suite performance
Was ~17 minutes for 235 tests (PBKDF2 hashing on every `User.objects.create_user()`).
Fixed 2026-08-19: `config/settings/dev.py` switches to `MD5PasswordHasher` when running under
`manage.py test`/`pytest`. Now **242 tests in ~6-12 seconds**.

## Postgres readiness — ✅ FULLY VERIFIED against a real live server (2026-08-20)
`config/settings/base.py`/`prod.py` hardening (`CONN_HEALTH_CHECKS`, `OPTIONS.sslmode`/`connect_timeout`,
prod-only fail-fast guards for `DB_ENGINE`/`DB_PASSWORD`) sat uncommitted for three sessions in a row
(2026-08-19 through 2026-08-20 morning) despite docs claiming it was done — see git history for when
that got fixed. The bigger gap was that the live-connection caveat below had never actually been closed.

**Closed 2026-08-20.** Spun up a real, disposable PostgreSQL 16.2 server locally (via the `pgserver`
PyPI package — a self-contained Postgres binary, no admin rights/Docker/system install needed; removed
again after verification, it's not a project dependency) and ran the project against it for real:
- `python manage.py migrate` under **both** `config.settings.dev` and `config.settings.prod` — every
  migration across all 14 apps applied cleanly to a fresh database, both times.
- `python manage.py test` (the **full 343-test suite**, unmodified) run against that live Postgres
  instead of SQLite — **all 343 passed**. This is the same run that caught the `Sum("point_awarded")`
  BooleanField bug (item #13) — proof the exercise catches real cross-database issues, not just a
  formality.
- `python manage.py check --deploy` under `config.settings.prod` with real secrets/`ALLOWED_HOSTS` —
  clean except the same pre-known benign `W004` (HSTS not set, a deliberate deploy-time decision).

One environment-specific snag, unrelated to Casset: the `pgserver` package's bundled Postgres binary
ships without the IANA timezone database (`share/postgresql/timezone` was entirely missing), so Django's
mandatory `SET TIME ZONE 'UTC'` on connect failed until real tzfiles were copied in from Git Bash's
MinGW64 install (`/mingw64/share/zoneinfo`). A normal PostgreSQL install/Docker image/managed service
(RDS, Supabase, etc.) always ships complete tzdata — this only affected this one throwaway test tool.

**Conclusion: the Postgres path is production-ready and proven, not just configured.** No further
smoke-test is required before the first real deploy on this account.

**Re-verified 2026-08-20 (final phase)** with the same pgserver-based disposable-Postgres method: full
413-test suite + `migrate` under both `dev`/`prod` settings — this run is what caught a second
`Sum(BooleanField)` bug (`core/staff_views.py::users_console`, same class as item #13) before it could
ever reach a real deploy. Fixed and re-verified clean. Test count: 343 → 413 over this session (SMS
provider, S3 storage validation, Celery task, health check, backup command, staff console — previously
completely unreachable, now tested — payment provider, payout approval, full-text search, OG tags,
thumbnail filter, and the two dashboards).
