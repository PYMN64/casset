# Controlled Agent Development v1.0

## English

Agents are development accelerators, not autonomous owners of Casset.

### Activation order
1. Brain is stable.
2. Test foundation exists.
3. CI can detect regressions.
4. A bounded developer agent is piloted.
5. Tester and reviewer agents are added.
6. Architect/security agents operate as approval layers for high-risk changes.

### Agent contract
Every agent receives: task scope, relevant Brain documents, allowed files/domains, acceptance criteria, required tests, and prohibited changes.

### Isolation
Agent changes should be performed on task branches. High-risk domains—play qualification, rewards, authentication, billing and migrations—require explicit review before merge.

### No self-evolution rule
Agents do not modify their own permissions, governance rules, source-of-truth policy, or architectural constitution.

## فارسی

Agentها شتاب‌دهنده توسعه هستند، نه مالک مستقل Casset.

### ترتیب فعال‌سازی
ابتدا Brain، سپس Test Foundation، بعد CI، سپس یک Developer Agent محدود، بعد Tester/Reviewer و در نهایت Agentهای Architect/Security به‌عنوان لایه تأیید تغییرات حساس.

### قرارداد Agent
هر Agent باید Scope، اسناد مرتبط Brain، فایل/Domain مجاز، Acceptance Criteria، تست‌های لازم و تغییرات ممنوع را دریافت کند.

### Isolation
تغییرات Agent روی Branch مستقل انجام شود. Domainهای حساس مثل Play Qualification، Reward، Authentication، Billing و Migration نیازمند Review صریح هستند.

### قانون عدم خودتکثیری
Agent حق تغییر Permission، Governance، Source of Truth یا Constitution خودش را ندارد.