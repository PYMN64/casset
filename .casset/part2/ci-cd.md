# CI/CD & Quality Gates v1.0

## English

### Goal
Every change should be reproducibly checked before it becomes part of the release branch.

### Pipeline
Push/PR → dependency install → formatting/lint checks → Django checks → unit/integration tests → security checks → build verification → deploy only after required gates pass.

### Initial gates
- deterministic dependency installation
- Python/Django compatibility check
- migrations check
- test suite
- static/lint checks
- basic security configuration checks

### Later gates
- coverage thresholds by critical domain
- dependency vulnerability scanning
- container/image scanning if containers are introduced
- deployment smoke tests
- rollback verification

### Branch policy
Part 1 feature work should remain isolated from Part 2 infrastructure changes where practical. Part 2 documentation is currently developed on `docs/part-2-engineering-foundation`; it does not alter `master` until reviewed.

## فارسی

### هدف
هر تغییر قبل از ورود به شاخه انتشار باید به‌صورت قابل تکرار بررسی شود.

### Pipeline
Push/PR → نصب Dependency → Format/Lint → Django Checks → Test → Security → Build Verification → Deploy.

### Gateهای اولیه
Dependency قابل تکرار، سازگاری Python/Django، بررسی Migration، تست، Lint و بررسی تنظیمات امنیتی.

### Gateهای بعدی
Coverage هدفمند، Vulnerability Scan، Image Scan در صورت نیاز، Smoke Test و Rollback Verification.

### سیاست Branch
تغییرات مهندسی Part 2 تا حد امکان از Featureهای Part 1 جدا هستند. این نسخه مستندات روی Branch جدا ساخته شده و تا زمان Review روی `master` وارد نمی‌شود.