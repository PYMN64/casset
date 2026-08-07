# Casset Technical Debt Register v1.0

## P0 — must resolve before or during core MVP work
- Add reproducible dependency management (`pyproject.toml` or equivalent).
- Establish pytest/pytest-django and meaningful regression coverage.
- Fix the known `AlbumForm` / `Album` field mismatch.
- Stop treating client-reported playback progress as proof of a qualified play.
- Introduce an auditable `PointLedger` instead of using `UserProfile.points` as the reward source of truth.
- Establish one canonical billing/subscription/entitlement model path.
- Make production configuration PostgreSQL-ready.
- Introduce object-storage-compatible media architecture.

## P1
- Extract Play/Upload/Reward services.
- Define `PlaybackSession` and `PlaybackEvent`.
- Add anti-fraud signals and risk evaluation.
- Add media metadata validation/extraction.
- Strengthen moderation lifecycle and immutable audit coverage.
- Add CI, logging, monitoring and backup strategy.

## P2
- Optimize discovery/trending using pre-aggregated statistics.
- Add recommendation capabilities only after real usage data exists.
