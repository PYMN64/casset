# Casset Constitution v1.0

## Mission
Casset is an Iran-first creator/listener audio platform. The initial product goal is a reliable, publishable MVP where creators can publish audio and listeners can consume it while the platform records trustworthy playback, analytics, and reward data.

## MVP business flow
User → Registration/Verification → Creator Onboarding → Upload → Media Validation → Draft → Moderation → Publish → Playback Session → Playback Events → Server Validation → Qualified Play → Analytics + Point Ledger → Creator Dashboard.

## Architecture principles
1. Keep the existing Django modular-monolith architecture; do not rewrite from scratch.
2. Business logic belongs in explicit service/domain boundaries rather than templates or oversized views.
3. Playback events are evidence; a client-reported progress value is never sufficient proof of a qualified play.
4. Qualified plays are server-validated and auditable.
5. Rewards are recorded through an immutable/auditable PointLedger; a profile counter is not the source of truth.
6. Track counters and dashboard aggregates are derived state and must be rebuildable from authoritative records.
7. Production must be PostgreSQL-ready and media storage must be object-storage compatible.
8. Important features require automated tests before they are considered Done.
9. Prefer a modular monolith for MVP. Do not introduce microservices, Kubernetes, or an event bus without evidence-based need.
10. Agents must read the Project Brain before changing architecture or core domains.

## Source of truth
- Repository code and `.casset/` are the canonical engineering source of truth.
- Notion is the canonical project-management/documentation mirror.
- When code and Brain diverge, the discrepancy must be recorded and resolved; agents must not silently redefine architecture.

## Definition of Done
A significant feature is Done only when requirement, architecture impact, implementation, automated tests, error handling, security considerations, documentation, migration impact, and review are addressed.
