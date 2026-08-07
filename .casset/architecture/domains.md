# Casset Domain Map v1.0

## Core domains
- `accounts`: identity, authentication, profile, creator lifecycle and permissions.
- `tracks`: track/album metadata and content lifecycle.
- `uploads`: upload validation, storage boundary and media processing.
- `plays`: playback sessions/events, qualification and anti-fraud signals.
- `moderation`: review queue, approval/rejection/takedown and audit trail.
- `explore`: search, discovery and trending.
- `interactions`: likes/follows and related social signals.
- `playlists`: listener playlists/library; MVP scope is intentionally limited.
- `billing` + `subscriptions`: retain the apps for now, but establish one canonical Plan/Subscription/Entitlement model before expanding billing.
- `core`: shared platform configuration and cross-cutting primitives.

## Core business graph
User → Creator → Track/Media → PlaybackSession → PlaybackEvent → QualifiedPlay → PointLedger → Analytics → Creator Dashboard.

## Domain decisions
1. `plays` is a core business domain and will receive an explicit service layer.
2. `uploads` will receive an explicit service boundary for validation, storage, metadata extraction and lifecycle transitions.
3. `PointLedger` becomes the authoritative reward record.
4. `Track.play_count` and similar counters are derived state.
5. No app is removed during Sprint 0 solely for cleanliness; consolidation happens only after domain contracts are understood.

## MVP freeze
The following are deliberately deferred: advanced recommendations, AI recommendation, chat, advanced social features, complex payout automation, microservices, Kubernetes, and event-bus infrastructure.
