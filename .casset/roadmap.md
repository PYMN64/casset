# Casset 90-Day Roadmap v1.0

## Part 1 — Publishable Professional MVP

### S0 Foundation
Project Brain, dependency management, environment, test foundation, P0 fixes, PostgreSQL readiness, architecture decisions.

### S1 Identity
Registration, OTP/verification, login, profile, creator onboarding, permissions.

### S2 Content
Track/Album stabilization, audio upload, validation, metadata, cover, draft/submit/publish lifecycle.

### S3 Moderation
Queue, approve, reject, block/takedown, report and audit trail.

### S4 Playback Core
Player integration, PlaybackSession, PlaybackEvent, heartbeat, server-side qualification.

### S5 Play Intelligence
Duplicate protection, fraud signals, risk evaluation, QualifiedPlay, PointLedger, reward rules and reversal.

### S6 Analytics
Track and creator statistics, aggregation, dashboard and admin statistics.

### S7 Discovery
Search, explore, trending and public creator profiles.

### S8 Production
PostgreSQL, Redis, background workers, object storage, production configuration, logging, monitoring, backup, security, deployment and beta verification.

## Part 2 — Engineering Foundation
Built alongside and after the MVP critical path: comprehensive tests, CI/CD, linting/formatting, architecture decision records, observability, security automation, performance work and controlled agent development.

## Release gate
The MVP is release-ready only when the full creator/listener flow completes without breaking: registration → verification → creator onboarding → upload → validation → moderation → publish → playback session → server validation → qualified play → analytics/points → creator dashboard.

## Part 3 — Phase 2 (post-v2.0.0)
MVP release gate above is met (v2.0.0, closed 2026-08-21). Full plan, competitive
analysis and S10–S13 sequencing: `.casset/releases/v2.1.0-phase2-plan.md`. Audit
that preceded it: `.casset/state/audit-2026-08-21.md`.
