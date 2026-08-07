# Test Strategy v1.0

## English

### Objective
Protect the Casset business-critical flow with the smallest test system that gives high confidence while the MVP is being built.

### Test pyramid
- Unit: domain rules and pure services; fast and numerous.
- Integration: Django models, database constraints, services, storage boundaries and external integrations.
- End-to-End: a small number of critical user journeys.

### Priority test domains
1. Authentication and authorization
2. Upload validation and lifecycle
3. Moderation transitions
4. PlaybackSession/Event behavior
5. Qualified-play rules
6. Fraud rules
7. PointLedger idempotency and reversal
8. Analytics aggregation
9. Creator dashboard critical queries

### Critical E2E scenario
Registration → verification → creator onboarding → upload → validation → moderation → publish → playback → qualified play → analytics/points → dashboard.

### Test rules
- A bug in a critical business rule requires a regression test.
- Tests must verify behavior, not implementation details, where practical.
- Never weaken a test merely to make a failing implementation pass.
- Database constraints and idempotency are explicitly tested.
- Time, randomness and external services should be controllable in tests.

### Release gates
A critical feature cannot be marked Done until its relevant unit/integration coverage exists. The release gate additionally requires the critical E2E flow to pass.

## فارسی

### هدف
با کمترین سیستم تستی که بیشترین اطمینان را ایجاد می‌کند، از مسیر حیاتی کسب‌وکار Casset در زمان ساخت MVP محافظت کنیم.

### هرم تست
- Unit برای قوانین Domain و Serviceهای خالص.
- Integration برای Model، Database، Service، Storage و Integrationها.
- End-to-End برای تعداد محدودی از مسیرهای حیاتی کاربر.

### اولویت تست
Authentication/Authorization، Upload، Moderation، PlaybackSession/Event، Qualified Play، Fraud، PointLedger، Analytics و Dashboard.

### قانون مهم
هر Bug در یک قانون مهم کسب‌وکار باید یک Regression Test ایجاد کند. تست نباید برای سبز شدن Build ضعیف شود.

### معیار انتشار
Feature مهم بدون تست متناسب Done نیست و انتشار بدون عبور مسیر کامل Creator/Listener مجاز نیست.