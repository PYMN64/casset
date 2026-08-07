# Casset MVP Release Flow v1.0

The first real Casset release must complete this flow without breaking:

User → Registration/Verification → Onboarding → Creator → Upload → Media Validation → Draft → Moderation → Publish → Listener → Play → Playback Session → Server Validation → Qualified Play → Analytics + Point → Creator Dashboard.

## Release gate
Every transition must have:
- explicit state/contract
- authorization checks
- error handling
- automated tests
- auditable data where business value is affected

## Critical trust rule
A client may report playback activity, but the server decides whether a play is qualified and rewardable.
