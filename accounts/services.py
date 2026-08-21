"""SMS delivery for phone OTP login.

Provider abstraction mirrors billing/services.py's payment-provider design
(built in the same session): swap providers via the SMS_PROVIDER env var
without touching call sites. ConsoleSmsProvider (the dev/test default) never
calls a real network API; KavenegarSmsProvider does, once a real API key is
configured — see config/settings/prod.py for the fail-fast guard that keeps
production from booting without one.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("casset.accounts")


class SmsSendError(Exception):
    """Raised when the configured SMS provider fails to deliver a message."""


class SmsProvider:
    def send(self, phone: str, message: str) -> None:
        raise NotImplementedError


class ConsoleSmsProvider(SmsProvider):
    """Dev/test provider — logs instead of sending over the network.

    The [DEV] code shown to the user in accounts/views.py::phone_start_view
    is a separate debug affordance (gated on settings.DEBUG); this provider
    only controls delivery, not that on-screen fallback.
    """

    def send(self, phone: str, message: str) -> None:
        logger.info("ConsoleSmsProvider: would send to %s: %s", phone, message)


class KavenegarSmsProvider(SmsProvider):
    """Real SMS delivery via Kavenegar (kavenegar.com) — the most common
    SMS/OTP provider for Iranian phone numbers.

    Uses the plain `sms/send.json` endpoint (API key + optional sender line,
    no template pre-registration needed) rather than Kavenegar's templated
    `verify/lookup.json` OTP endpoint — simpler to stand up with just an API
    key. Swap the URL/params here if a project later wants the templated
    endpoint instead.
    """

    BASE_URL = "https://api.kavenegar.com/v1/{api_key}/sms/send.json"

    def __init__(self, api_key: str, sender: str = ""):
        self.api_key = api_key
        self.sender = sender

    def send(self, phone: str, message: str) -> None:
        url = self.BASE_URL.format(api_key=self.api_key)
        params = {"receptor": phone, "message": message}
        if self.sender:
            params["sender"] = self.sender
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error("Kavenegar SMS send failed for %s: %s", phone, exc)
            raise SmsSendError(str(exc)) from exc

        status = (payload.get("return") or {}).get("status")
        if status != 200:
            reason = (payload.get("return") or {}).get("message", "unknown error")
            logger.error("Kavenegar SMS rejected for %s: %s", phone, reason)
            raise SmsSendError(reason)


def get_sms_provider() -> SmsProvider:
    provider = getattr(settings, "SMS_PROVIDER", "console")
    if provider == "kavenegar":
        return KavenegarSmsProvider(
            api_key=settings.KAVENEGAR_API_KEY,
            sender=getattr(settings, "KAVENEGAR_SENDER", ""),
        )
    return ConsoleSmsProvider()


def send_otp_sms(phone: str, code: str) -> None:
    """Send an OTP code to *phone*.

    Never raises to the caller: SMS delivery failure must not break the
    login flow (the code is still valid/checkable if the user somehow gets
    it, and a retry is one tap away) — the failure is logged at ERROR level
    so a provider outage is visible in ops/Sentry rather than silent.
    """
    provider = get_sms_provider()
    message = f"کد ورود کست: {code}"
    try:
        provider.send(phone, message)
    except SmsSendError:
        logger.error(
            "OTP SMS delivery failed for %s (provider=%s)",
            phone,
            provider.__class__.__name__,
        )


# ===========================================================================
# Authentication domain services
#
# Everything below is the decision-making half of sign-in: issuing and
# checking OTPs, and turning a verified Google identity into a Casset
# account. It lives here, not in views.py, so the same rules apply whether
# the caller is the login page, the "add a phone to my account" flow, or a
# future API client (Constitution: business logic belongs in the service
# layer).
# ===========================================================================

#: How long a code stays usable. Short on purpose: an OTP is a bearer
#: token for a whole account.
OTP_TTL = timedelta(minutes=2)
#: Wrong guesses tolerated per issued code before it is burned.
OTP_MAX_ATTEMPTS = 5
#: Minimum gap between two sends to the same number.
OTP_RESEND_COOLDOWN_SECONDS = 60

#: Persian and Arabic-Indic digits, mapped to ASCII. A Farsi keyboard
#: produces these, and every phone/OTP field must accept them.
_DIGIT_TRANS = str.maketrans("۰۱۲۳۴۵۶۷۸۹"
                             "٠١٢٣٤٥٦٧٨٩",
                             "01234567890123456789")


def normalize_phone(phone: str) -> str:
    """Reduce the many ways an Iranian mobile number gets typed to one form.

    +989121234567 / 989121234567 / 0912 123 4567 all become 09121234567,
    so the uniqueness constraint on UserProfile.phone_number actually means
    "one account per phone".
    """
    p = (phone or "").strip()
    for ch in (" ", "-", "(", ")"):
        p = p.replace(ch, "")
    p = p.translate(_DIGIT_TRANS)
    if p.startswith("+98"):
        p = "0" + p[3:]
    elif p.startswith("0098"):
        p = "0" + p[4:]
    elif p.startswith("98") and len(p) >= 12:
        p = "0" + p[2:]
    elif p.startswith("9") and len(p) == 10:
        p = "0" + p
    return p


def is_valid_iran_mobile(phone: str) -> bool:
    """09 followed by 9 digits, which is every Iranian mobile number."""
    p = normalize_phone(phone)
    return len(p) == 11 and p.startswith("09") and p.isdigit()


def hash_otp_code(phone: str, code: str) -> str:
    """Codes are stored hashed and salted by the phone number, so a database
    read never yields a usable code for a different number."""
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def generate_username() -> str:
    """Opaque internal username.

    Never derived from the phone number or email: usernames appear in
    /@username/ URLs, and deriving one would leak a personal identifier to
    anyone who can see a profile link.
    """
    token = secrets.token_urlsafe(9).replace("-", "").replace("_", "")
    return f"u-{token[:10]}"


def unique_username() -> str:
    user_model = get_user_model()
    username = generate_username()
    while user_model.objects.filter(username=username).exists():
        username = generate_username()
    return username


def issue_otp(phone: str, *, ip_address=None, user_agent: str = ""):
    """Create and send a fresh OTP for *phone*.

    Returns (ok, payload). On success payload is the plaintext code, which
    the caller only ever surfaces under DEBUG. On failure it is an error
    code: "invalid_phone" or "cooldown".
    """
    from .models import PhoneOTP

    if not is_valid_iran_mobile(phone):
        return False, "invalid_phone"

    phone = normalize_phone(phone)
    now = timezone.now()

    last = PhoneOTP.objects.filter(phone_number=phone).order_by("-created_at").first()
    if last and last.last_sent_at:
        elapsed = (now - last.last_sent_at).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            return False, "cooldown"

    code = f"{secrets.randbelow(1000000):06d}"
    PhoneOTP.objects.create(
        phone_number=phone,
        code_hash=hash_otp_code(phone, code),
        expires_at=now + OTP_TTL,
        last_sent_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:256],
    )
    send_otp_sms(phone, code)
    return True, code


def verify_otp(phone: str, code: str):
    """Check *code* against the newest unused OTP for *phone*.

    Returns (ok, error_code) where error_code is one of "not_found",
    "expired", "too_many_attempts", "wrong_code". A correct code is burned
    (is_used=True) inside the same transaction that validates it, so the
    same code cannot be redeemed twice by concurrent requests.
    """
    from .models import PhoneOTP

    phone = normalize_phone(phone)
    code = (code or "").strip().translate(_DIGIT_TRANS)

    with transaction.atomic():
        otp = (
            PhoneOTP.objects.select_for_update()
            .filter(phone_number=phone, is_used=False)
            .order_by("-created_at")
            .first()
        )
        if not otp:
            return False, "not_found"
        if otp.expires_at < timezone.now():
            return False, "expired"
        if otp.attempts >= OTP_MAX_ATTEMPTS:
            return False, "too_many_attempts"

        if not secrets.compare_digest(otp.code_hash, hash_otp_code(phone, code)):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            return False, "wrong_code"

        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return True, ""


OTP_ERROR_MESSAGES = {
    "invalid_phone": "شماره موبایل معتبر نیست. نمونه درست: ۰۹۱۲۱۲۳۴۵۶۷",
    "cooldown": "کد قبلی هنوز معتبر است. لطفاً یک دقیقه صبر کن.",
    "not_found": "کدی برای این شماره ثبت نشده. دوباره درخواست بده.",
    "expired": "کد منقضی شده. دوباره درخواست بده.",
    "too_many_attempts": "تعداد تلاش‌ها بیش از حد مجاز است. کد جدید بگیر.",
    "wrong_code": "کد وارد شده اشتباه است.",
    "rate_limited": "درخواست‌های زیادی از این دستگاه ارسال شده. کمی صبر کن.",
    "phone_taken": "این شماره قبلاً به حساب دیگری متصل شده است.",
}


@transaction.atomic
def resolve_google_user(identity: dict):
    """Turn a verified Google identity into a Casset user.

    Match order matters:
      1. google_sub — Google's immutable subject id. Matching on this first
         means a user who changes their Gmail address keeps their account.
      2. email — links Google to an account that already signed up with the
         same address by password or phone, instead of creating a duplicate.
      3. otherwise, create a new account.

    Only reached with an already-verified email (accounts/oauth.py refuses
    unverified ones), which is what makes step 2 safe: without that check,
    step 2 would be an account-takeover path.

    Returns (user, created).
    """
    from .models import UserProfile

    user_model = get_user_model()
    sub = identity["sub"]
    email = identity["email"]

    profile = UserProfile.objects.filter(google_sub=sub).select_related("user").first()
    if profile:
        return profile.user, False

    user = user_model.objects.filter(email__iexact=email).order_by("id").first()
    created = False
    if user is None:
        user = user_model.objects.create(username=unique_username(), email=email)
        # No password is set: this account signs in through Google. An
        # unusable password cannot be brute-forced, and the user can still
        # add one later through password reset if they want a second method.
        user.set_unusable_password()
        if identity.get("name"):
            parts = identity["name"].split(" ", 1)
            user.first_name = parts[0][:150]
            user.last_name = (parts[1] if len(parts) > 1 else "")[:150]
        user.save()
        created = True

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.google_sub = sub
    profile.email_verified_at = profile.email_verified_at or timezone.now()
    if created:
        profile.auth_provider = UserProfile.AuthProvider.GOOGLE
        if identity.get("name") and not profile.display_name:
            profile.display_name = identity["name"][:80]
    profile.save(update_fields=[
        "google_sub", "email_verified_at", "auth_provider", "display_name",
    ])
    return user, created



# ===========================================================================
# Email verification (password sign-up only — Google already proves the
# address, and phone OTP doesn't use one). See accounts/views.py::
# register_view / verify_email_view / resend_verification_email_view.
# ===========================================================================

#: How long a verification link stays usable. Longer than the OTP TTL on
#: purpose: this arrives by e-mail, which people check less immediately
#: than an SMS, and the account is merely inert (not published/dangerous)
#: while unverified.
EMAIL_VERIFICATION_TTL = timedelta(hours=24)
#: Minimum gap between two verification e-mails to the same account.
EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = 60


def _hash_email_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def send_verification_email(user, request, token: str) -> None:
    """E-mail *user* a verification link built from a live request, so it
    points at whatever host actually served the request — the same
    approach Django's own PasswordResetForm uses via get_current_site.

    Never raises: like send_otp_sms, a delivery failure must not break
    sign-up. It's logged so a provider/SMTP outage is visible in
    ops/Sentry rather than silent.
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.urls import reverse
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse("verify_email", kwargs={"uidb64": uid, "token": token})
    context = {"user": user, "verify_url": request.build_absolute_uri(path)}
    subject = render_to_string("accounts/verification_email_subject.txt", context).strip()
    body = render_to_string("accounts/verification_email.txt", context)
    try:
        send_mail(subject, body, None, [user.email], fail_silently=False)
    except Exception:
        logger.exception("send_verification_email: failed for user=%s", user.id)


def issue_email_verification(user, request) -> str:
    """Create and send a fresh e-mail verification token for *user*.

    Returns the plaintext token — production callers only need the side
    effect (the e-mail); tests use the return value to verify without
    parsing an outbox message.
    """
    from .models import EmailVerification

    token = secrets.token_urlsafe(32)
    EmailVerification.objects.create(
        user=user,
        token_hash=_hash_email_token(token),
        expires_at=timezone.now() + EMAIL_VERIFICATION_TTL,
    )
    send_verification_email(user, request, token)
    return token


def seconds_until_email_resend(user) -> int:
    """Mirrors `_seconds_until_resend` for phone OTP, keyed to a user
    instead of a phone number."""
    from .models import EmailVerification

    last = EmailVerification.objects.filter(user=user).order_by("-created_at").first()
    if not last:
        return 0
    elapsed = (timezone.now() - last.created_at).total_seconds()
    return max(0, int(EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed))


def find_unverified_user_by_email(email: str):
    """Look up an account eligible for a *resend* of its verification link.

    Returns None for "no such account", "already verified", or "not a
    password account" alike — the caller (resend view) must show the same
    generic message in every case, or the endpoint becomes an oracle for
    testing which e-mails have an account on Casset.
    """
    from .models import UserProfile

    email = (email or "").strip().lower()
    if not email:
        return None

    user_model = get_user_model()
    user = (
        user_model.objects.filter(email__iexact=email, is_active=False)
        .select_related("profile")
        .order_by("id")
        .first()
    )
    if not user:
        return None

    profile = getattr(user, "profile", None)
    if profile is None or profile.auth_provider != UserProfile.AuthProvider.PASSWORD:
        return None
    if profile.email_verified:
        return None
    return user


def verify_email_token(uidb64: str, token: str):
    """Redeem an e-mail verification link.

    Returns (ok, user_or_none, error_code). error_code is one of
    "bad_link" or "expired". Burns the row inside a transaction so the
    same link cannot be redeemed twice by concurrent requests; clicking an
    already-used-but-valid link again is treated as success (idempotent —
    the account is already verified) rather than an error.
    """
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    from .models import EmailVerification, UserProfile

    user_model = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = user_model.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, user_model.DoesNotExist):
        return False, None, "bad_link"

    token_hash = _hash_email_token(token)
    with transaction.atomic():
        record = (
            EmailVerification.objects.select_for_update()
            .filter(user=user, token_hash=token_hash)
            .first()
        )
        if not record:
            return False, None, "bad_link"

        if record.is_used:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if profile.email_verified:
                return True, user, ""
            return False, None, "bad_link"

        if record.expires_at < timezone.now():
            return False, None, "expired"

        record.is_used = True
        record.save(update_fields=["is_used"])

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified_at"])

    user.is_active = True
    user.save(update_fields=["is_active"])

    return True, user, ""


def attach_phone_to_user(user, phone: str):
    """Bind a freshly-verified phone number to an existing account.

    Refuses a number already bound elsewhere rather than stealing it — the
    uniqueness constraint would raise anyway; this turns that into a clean
    user-facing error. This is the step that unlocks publishing
    (UserProfile.can_publish).

    Returns (ok, error_code).
    """
    from .models import UserProfile

    phone = normalize_phone(phone)
    clash = (
        UserProfile.objects.filter(phone_number=phone)
        .exclude(user_id=user.id)
        .exists()
    )
    if clash:
        return False, "phone_taken"

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.phone_number = phone
    profile.phone_verified_at = timezone.now()
    profile.save(update_fields=["phone_number", "phone_verified_at"])
    return True, ""
