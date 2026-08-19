# Casset Current State

## Status
Audit complete. MVP definition and architecture direction are established. Sprint 0 is the active milestone.

## Repository strategy
Keep the existing Django modular monolith. Stabilize and refactor critical domains instead of rewriting.

## Current critical path
S0 Foundation → S1 Identity → S2 Content → S3 Moderation → S4 Playback → S5 Play Intelligence → S6 Analytics → S7 Discovery → S8 Production.

## Current release criterion
The creator/listener business flow must work end-to-end and produce trustworthy qualified-play, analytics and reward records.

## Agent status
Agent system is designed but intentionally not activated as autonomous development infrastructure until Brain + test foundation are in place.

## Change log index
All architectural changes are recorded in `.casset/state/changelog.md`.
Read that file at the start of every session to know what has changed and why.

## Test coverage baseline (2026-08-19)
`coverage run --source=. manage.py test` → **81% overall** (242 tests, 2640 statements, 494 missed).
Full HTML report regeneratable with `coverage html`; not committed (`.gitignore`d).

Notably low (real gaps, not noise):
- `interactions/views.py` — 22% (likes/follows/comments — the social layer the product identity depends on)
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
