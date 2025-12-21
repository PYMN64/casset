import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_otp(phone: str, code: str) -> bool:
    """Mock SMS sender for OTP codes.

    Replace with a real provider later.
    """
    if settings.DEBUG:
        logger.info("DEV OTP for %s: %s", phone, code)
    return True
