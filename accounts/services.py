"""SMS delivery for phone OTP login.

Provider abstraction mirrors billing/services.py's payment-provider design
(built in the same session): swap providers via the SMS_PROVIDER env var
without touching call sites. ConsoleSmsProvider (the dev/test default) never
calls a real network API; KavenegarSmsProvider does, once a real API key is
configured — see config/settings/prod.py for the fail-fast guard that keeps
production from booting without one.
"""

import logging

import requests
from django.conf import settings

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
