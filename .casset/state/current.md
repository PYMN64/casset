# Casset Current State

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

## Repository strategy
Keep the existing Django modular monolith. Stabilize and refactor critical domains instead of rewriting.

## Current critical path
S0 Foundation ✅ → S1 Identity ✅ → S2 Content/Social ✅ → S3 Moderation ✅ → S4 Playback ✅ → S5 Play Intelligence ✅ → S6 Analytics ✅ → S7 Discovery ✅ → **S8 Production (next)**.

## Current release criterion
The creator/listener business flow must work end-to-end and produce trustworthy qualified-play, analytics and reward records.

## Agent status
Agent system is designed but intentionally not activated as autonomous development infrastructure until Brain + test foundation are in place.

## Change log index
All architectural changes are recorded in `.casset/state/changelog.md`.
Read that file at the start of every session to know what has changed and why.

## Test coverage baseline (2026-08-19, pre-Phase-2-delivery)
`coverage run --source=. manage.py test` → **81% overall** (242 tests, 2640 statements, 494 missed).
Full HTML report regeneratable with `coverage html`; not committed (`.gitignore`d).
Superseded by Phase 2 (242 → 286), Phase 3 (286 → 318), and Phase 4+5 (318 → 343) deliveries below;
coverage not re-measured yet — `interactions` (0 → 42 tests) and `explore` (0 → 16 tests) in particular
should now score far above the numbers listed here. Re-run `coverage html` before trusting these
per-file numbers again.

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
