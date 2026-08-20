"""Settings package — never a usable settings module on its own.

This package used to do `from .dev import *`, which made a bare
`DJANGO_SETTINGS_MODULE=config.settings` silently resolve to **development**
settings: DEBUG=True, insecure cookies, no SSL redirect, SQLite, and a
throwaway auto-generated SECRET_KEY. On a production host that is a silent,
catastrophic misconfiguration — exactly the class of failure the explicit
fail-fast guards in prod.py exist to prevent.

Now the choice must be explicit: config.settings.dev or config.settings.prod.

The guard is conditional rather than an unconditional `raise`, because
Python imports a parent package before its submodules — raising here
unconditionally would also break the legitimate `config.settings.dev` and
`config.settings.prod` imports.
"""

import os

if os.environ.get("DJANGO_SETTINGS_MODULE") == "config.settings":
    raise ImportError(
        "DJANGO_SETTINGS_MODULE=config.settings is not a valid settings module. "
        "Choose explicitly: 'config.settings.dev' for local development or "
        "'config.settings.prod' for production. (A bare 'config.settings' used "
        "to silently mean dev — including DEBUG=True — which is unsafe in prod.)"
    )
