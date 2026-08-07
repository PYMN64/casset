# Performance & Reliability Policy v1.0

## English

Performance work follows measurement, not speculation.

### Initial focus
- database indexes for high-volume queries
- N+1 query prevention
- bounded pagination
- caching only measured hot paths
- background processing for expensive media/analytics jobs
- idempotent workers and reward operations
- transaction boundaries around authoritative business writes

### Reliability priorities
1. Data integrity
2. Correct qualified-play decisions
3. Correct reward accounting
4. Availability of critical user flows
5. Latency optimization

### Rule
Do not introduce distributed infrastructure simply to anticipate scale. Scale the modular monolith based on observed bottlenecks.

## فارسی

Performance باید بر اساس Measurement انجام شود، نه حدس.

### تمرکز اولیه
Index، جلوگیری از N+1، Pagination محدود، Cache فقط برای مسیرهای واقعاً داغ، Background Job برای Media/Analytics، Idempotency و Transaction Boundary برای Writeهای مهم.

### اولویت Reliability
یکپارچگی داده → صحت Qualified Play → صحت Reward → دسترس‌پذیری Flowهای اصلی → بهینه‌سازی Latency.

### قانون
برای پیش‌بینی رشد، زیرساخت Distributed اضافه نمی‌کنیم. ابتدا Modular Monolith را بر اساس Bottleneck واقعی Scale می‌کنیم.