# Security Engineering Baseline v1.0

## English

Security is a cross-cutting requirement. Part 2 establishes a baseline without blocking normal MVP development.

### Required areas
- authentication and authorization boundaries
- OTP abuse/rate limiting
- CSRF/session security
- upload type, size, content and filename validation
- safe media processing
- access control for private media
- admin/moderator authorization
- rate limiting for high-value endpoints
- audit logging for moderation and reward-affecting actions
- secrets and environment isolation
- dependency vulnerability review

### Casset-specific trust boundary
The browser is an untrusted source. Client playback events are telemetry, not authoritative reward evidence. Server-side rules determine Qualified Play.

## فارسی

امنیت یک نیاز Cross-cutting است. Part 2 یک Baseline امنیتی ایجاد می‌کند بدون اینکه توسعه عادی MVP را متوقف کند.

### حوزه‌های الزامی
Authentication/Authorization، محدودیت OTP، Session/CSRF، اعتبارسنجی Upload، پردازش امن Media، دسترسی Media خصوصی، سطح دسترسی Admin/Moderator، Rate Limit، Audit Log، Secrets و بررسی آسیب‌پذیری Dependencyها.

### مرز اعتماد Casset
Browser قابل اعتماد نیست. Eventهای Playback ارسال‌شده از Client فقط Telemetry هستند و به‌تنهایی مدرک Reward نیستند. تصمیم Qualified Play باید سمت Server گرفته شود.