#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Load .env file before Django reads any settings.
    # This must happen before os.environ.setdefault so that values in .env
    # take precedence over system-level env vars in dev.
    try:
        from dotenv import load_dotenv
        load_dotenv()  # looks for .env in cwd and parent dirs
    except ImportError:
        pass  # dotenv not installed — rely on OS env vars (CI/prod)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
