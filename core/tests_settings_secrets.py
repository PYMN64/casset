"""core/tests_settings_secrets.py — S10 item 3: confirm SECRET_KEY,
PLAY_IP_SALT and PLAY_UA_SALT are actually fail-fast in a production-shaped
environment, and that the dev fallback still lets local development run
without a .env file.

`config/settings/base.py::_require_secret` was already written this way;
these are regression tests proving it, not a behavior change. Two layers:

- `RequireSecretFailFastTests` exercises the helper function directly and
  fast (no subprocess) for the two branches (dev_fallback True/False).
- `ProdSettingsBootTests` actually boots a fresh, separate Python process
  with `DJANGO_SETTINGS_MODULE=config.settings.prod` to prove the guard
  fires at real startup, not just in the helper in isolation — the same
  distinction CLAUDE.md's audit history flags for prod-only bugs that unit
  tests under dev settings can't see (e.g. the SUM(BooleanField) bugs).
"""

import os
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings.base import _require_secret


class RequireSecretFailFastTests(SimpleTestCase):
    def test_missing_var_without_dev_fallback_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                _require_secret("SOME_TOTALLY_UNSET_TEST_VAR", dev_fallback=False)

    def test_missing_var_with_dev_fallback_generates_a_usable_value(self):
        with patch.dict(os.environ, {}, clear=True):
            value = _require_secret("SOME_TOTALLY_UNSET_TEST_VAR", dev_fallback=True)
        self.assertIsInstance(value, str)
        self.assertGreaterEqual(len(value), 32)

    def test_present_var_is_returned_verbatim_regardless_of_fallback(self):
        with patch.dict(os.environ, {"SOME_TEST_VAR": "explicit-value"}):
            self.assertEqual(
                _require_secret("SOME_TEST_VAR", dev_fallback=False), "explicit-value"
            )
            self.assertEqual(
                _require_secret("SOME_TEST_VAR", dev_fallback=True), "explicit-value"
            )


class ProdSettingsBootTests(SimpleTestCase):
    """Spawns `python -c "import django; django.setup()"` in a subprocess
    with a hand-built environment — the only way to actually observe
    module-level startup failure, since the current process already has
    config.settings.dev loaded and cached in sys.modules.
    """

    REQUIRED_SECRETS = ("DJANGO_SECRET_KEY", "PLAY_IP_SALT", "PLAY_UA_SALT")

    def _base_env(self) -> dict:
        return {
            "PATH": os.environ.get("PATH", ""),
            "DJANGO_SETTINGS_MODULE": "config.settings.prod",
            "DJANGO_SECRET_KEY": "s" * 64,
            "PLAY_IP_SALT": "i" * 64,
            "PLAY_UA_SALT": "u" * 64,
            # The rest of prod.py's own fail-fast guards (DB/SMS/payment) —
            # supplied so a missing *secret* is what fails, not one of
            # those unrelated requirements.
            "DJANGO_ALLOWED_HOSTS": "casset.example.com",
            "DB_ENGINE": "postgresql",
            "DB_PASSWORD": "test-password",
            "SMS_PROVIDER": "kavenegar",
            "KAVENEGAR_API_KEY": "test-key",
            "PAYMENT_PROVIDER": "zarinpal",
            "ZARINPAL_MERCHANT_ID": "test-merchant",
        }

    def _boot(self, env: dict):
        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=str(django_settings.BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_boots_cleanly_when_all_three_secrets_are_set(self):
        result = self._boot(self._base_env())
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_missing_each_secret_individually_fails_fast(self):
        for var in self.REQUIRED_SECRETS:
            with self.subTest(missing=var):
                env = self._base_env()
                del env[var]
                result = self._boot(env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)
                self.assertIn(var, result.stderr)

    def test_blank_secret_value_also_fails_fast(self):
        """An env var present but set to an empty string must be treated
        the same as unset — a blank override in a deploy tool is a real
        way this could otherwise slip through."""
        env = self._base_env()
        env["PLAY_UA_SALT"] = ""
        result = self._boot(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PLAY_UA_SALT", result.stderr)
