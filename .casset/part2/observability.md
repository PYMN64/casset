# Observability Baseline v1.0

## English

Casset must be diagnosable in production. The first version focuses on actionable signals rather than a large monitoring stack.

### Logs
Structured application logs for authentication failures, uploads, moderation decisions, playback qualification decisions, reward changes and background jobs.

### Metrics
Start with request errors/latency, upload failures, playback session failures, qualified-play rate, fraud rejection rate, reward ledger operations and worker failures.

### Health
Provide application, database, cache and worker health checks appropriate to the deployment architecture.

### Alerts
Alert only on conditions that require action: sustained error rate, worker failure, database/storage failure, abnormal playback qualification drop and reward-processing anomalies.

## فارسی

Casset باید در Production قابل عیب‌یابی باشد. نسخه اول به جای ساخت یک Monitoring Stack سنگین، روی Signalهای عملی تمرکز می‌کند.

### Logs
Log ساختاریافته برای Authentication Failure، Upload، Moderation، تصمیم Qualified Play، تغییر Reward و Jobها.

### Metrics
Error/Latency، شکست Upload، شکست Session، نرخ Qualified Play، نرخ Fraud Rejection، عملیات PointLedger و خطای Worker.

### Health
Health Check برای Application، Database، Cache و Worker متناسب با معماری Deployment.

### Alerts
فقط موارد قابل اقدام Alert شوند: خطای پایدار، شکست Worker، خرابی Database/Storage، افت غیرعادی Qualified Play و ناهنجاری Reward.