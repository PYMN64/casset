# Casset S0.2 — Dependency & Environment Foundation

**Date:** 2026-08-08
**Project version:** 0.1.0
**Phase:** S0 Foundation
**Status:** Implemented — runtime verification pending
**Baseline branch:** `baseline/pre-s0.1-2026-08-08`

## Objective
Establish a canonical Python dependency contract and make runtime/database configuration environment-driven without introducing product behavior changes.

## Changes implemented
1. Added root `pyproject.toml` as the canonical Python project/dependency contract.
2. Declared supported Python runtime as `>=3.12,<3.15` and Django as `>=6.0,<6.1`.
3. Added PostgreSQL driver (`psycopg[binary]`) and Redis client dependencies required by the existing configuration model.
4. Added development test dependencies (`pytest`, `pytest-django`) as an optional `dev` extra.
5. Formalized `.env.example` with Django, database, Redis, playback, upload, and production-security variables.
6. Updated `config/settings.py` so DEBUG, hosts, CSRF origins, timezone, Redis, playback values, and database selection are environment-driven.
7. Added explicit `DB_ENGINE` support for `sqlite` and `postgresql`; SQLite remains the local default, while PostgreSQL can be selected without source-code changes.
8. Changed the default `DJANGO_DEBUG` behavior to disabled when the environment variable is absent.

## Deliberately not changed
- Product/domain behavior
- Models and migrations
- Playback qualification logic
- Reward/points logic
- Upload workflow behavior
- Billing/subscription behavior
- Media storage implementation
- Docker/containerization
- CI/CD workflows

## Verification status
Static repository review was completed before implementation. Full runtime verification (dependency installation, Django system checks, migrations, and test execution) requires an executable project environment; this GitHub integration can modify and inspect repository files but does not execute the repository runtime.

## Next gate
S0.2 is not considered fully closed until runtime verification is performed in the development environment/CI. After that, proceed to S0.3 — Test Foundation.
