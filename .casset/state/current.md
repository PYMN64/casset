# Casset Current State

## Status
Phase 1 (Foundation Stabilization) **closed** 2026-08-19 — all 8 items in CLAUDE.md §3 resolved.
Phase 2 (revised — social endpoints + player UX, roadmap §7) **closed** 2026-08-19 — items #9/#10 resolved.
Phase 3 (Moderation) is now the active milestone.

## Repository strategy
Keep the existing Django modular monolith. Stabilize and refactor critical domains instead of rewriting.

## Current critical path
S0 Foundation ✅ → S1 Identity ✅ → **S2 Content/Social (closing)** → S3 Moderation (active) → S4 Playback → S5 Play Intelligence → S6 Analytics → S7 Discovery → S8 Production.

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
Superseded same day by the Phase 2 delivery below (242 → 286 tests); coverage not re-measured yet —
`interactions` in particular should now score far above the 22% listed here since it went from 0
tests to 34. Re-run `coverage html` before trusting these per-file numbers again.

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

## Postgres readiness (Phase 1 closing item, 2026-08-19)
`config/settings/base.py` and `config/settings/prod.py` were audited and hardened — full detail in
`.casset/state/changelog.md`. Summary: `DB_ENGINE=postgresql` support already existed but was
untested and under-hardened; added `CONN_HEALTH_CHECKS`, `OPTIONS.sslmode`/`connect_timeout`, and
prod-only fail-fast guards (reject `DB_ENGINE=sqlite`, require `DB_PASSWORD`, default `sslmode` to
`require`). Verified: `manage.py check`/`check --deploy` load cleanly with simulated postgresql env
vars, all 4 new guard/default behaviors confirmed by direct test, full 242-test suite still green
on sqlite, `makemigrations --check` clean, `ruff check` clean on changed files.
**Not verified: an actual live connection/`migrate` against a running PostgreSQL server** — no
Postgres or Docker install was available on this machine. This is a required manual smoke test
before the first real production deploy.
