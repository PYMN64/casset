# Casset Part 2 — Professional Engineering Foundation

> Part 2 is an engineering-quality layer around the MVP. It must improve reliability without expanding or redefining the MVP product scope.

## English

Part 2 exists to make Casset **testable, reviewable, observable, secure, maintainable, and safely extensible**.

It is deliberately isolated under `.casset/part2/` so its planning documents do not overwrite or blur Part 1 product requirements. Part 2 changes may support Part 1, but they do not create permission to delay the MVP critical path.

### Separation rule
- Part 1 defines **what the product must do to ship**.
- Part 2 defines **how safely and professionally we build, verify, operate, and extend it**.
- A Part 2 item may become a release gate only when it protects a concrete Part 1 requirement or production risk.

### Engineering layers
1. Test Foundation
2. CI/CD and Quality Gates
3. Architecture Decision Records
4. Security Engineering
5. Observability
6. Performance and Reliability
7. Data Integrity and Migration Discipline
8. Controlled Agent Development
9. Architecture Drift Auditing

### Non-goals
Part 2 does not introduce microservices, Kubernetes, an event bus, advanced AI recommendations, or speculative infrastructure merely for technical sophistication.

## فارسی

پارت ۲ یک لایه مهندسی حرفه‌ای در کنار MVP است تا Casset **قابل تست، قابل بازبینی، قابل مانیتور، امن، قابل نگهداری و قابل توسعه** باشد.

این بخش عمداً در `.casset/part2/` جدا شده تا مستندات مهندسی با نیازمندی‌های محصول Part 1 مخلوط نشوند. Part 2 از Part 1 پشتیبانی می‌کند، اما نباید بدون دلیل مسیر انتشار MVP را متوقف کند.

### قانون جداسازی
- Part 1 مشخص می‌کند **محصول برای انتشار چه کاری باید انجام دهد**.
- Part 2 مشخص می‌کند **چطور آن را حرفه‌ای، امن و قابل اتکا می‌سازیم و توسعه می‌دهیم**.
- یک مورد Part 2 فقط زمانی Gate انتشار می‌شود که مستقیماً از یک نیاز حیاتی MVP یا ریسک Production محافظت کند.

### لایه‌های مهندسی
تست، CI/CD، تصمیمات معماری، امنیت، Observability، کارایی و پایداری، یکپارچگی داده، توسعه کنترل‌شده Agentها و Audit معماری.

### خارج از محدوده
فعلاً Microservice، Kubernetes، Event Bus، Recommendation AI و زیرساخت‌های پیچیده و بدون نیاز واقعی ساخته نمی‌شوند.