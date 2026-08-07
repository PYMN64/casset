# Part 3 — Execution Layer v1.0

## English
Part 3 is the execution layer of Casset. It does not introduce a new Django app, service, or product architecture. It governs how the approved Product (Part 1) and Engineering Foundation (Part 2) are turned into tested repository changes.

### Execution loop
Inspect → Plan → Change → Test → Review → Document → Commit/Merge.

### Scope
- Sprint plans and acceptance criteria
- bounded implementation tasks
- database/code changes
- regression tests
- review and release gates
- change log and project-state updates

### Boundaries
Part 3 must not redefine Part 1 product scope or bypass Part 2 engineering rules. Architecture changes require an explicit decision record. Agents operate under the same execution protocol and do not become an independent source of truth.

## فارسی
پارت ۳ لایه اجرای پروژه است؛ نه یک Django App و نه یک معماری جداگانه. این بخش مشخص می‌کند تصمیمات Part 1 و استانداردهای Part 2 چگونه به تغییرات واقعی، تست‌شده و قابل بررسی در Repository تبدیل شوند.

چرخه اجرا:
بررسی → برنامه‌ریزی → تغییر → تست → بازبینی → مستندسازی → Commit/Merge

پارت ۳ شامل Sprintها، Taskها، معیار پذیرش، تغییرات کد و دیتابیس، تست Regression، Review، Release Gate و Change Log است. این بخش حق تغییر خودسرانه Product یا Architecture را ندارد و Agentها نیز باید همین پروتکل را رعایت کنند.
