# Casset Current Architecture State v1.0

## Assessment
The repository is a viable modular Django foundation. A rewrite is not justified.

## Domain map
accounts, tracks, uploads, plays, moderation, explore, interactions, playlists, billing, subscriptions, core.

## Main architectural risks
- Business logic is too concentrated in some views, especially playback.
- Upload flow lacks a strong service boundary.
- Playback qualification currently relies too heavily on client-supplied signals.
- Reward accounting lacks an auditable ledger.
- Billing and subscription concepts overlap.
- Local file storage is not production-ready.
- Test coverage is insufficient for core business behavior.

## Target direction
HTTP/API → View → Service/Domain Logic → Model/Repository boundary.

The MVP remains a modular monolith. Redis, workers, PostgreSQL and object storage are introduced where they solve concrete MVP/production requirements; microservices are deferred.
