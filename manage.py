#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

from django.core.management.commands.runserver import Command as runserver


runserver.default_port = os.environ.get("DJANGO_PORT", "8000")
runserver.default_addr = os.environ.get("DJANGO_INTERFACE", "127.0.0.1")


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
    os.environ.setdefault("DJANGO_CONFIGURATION", "Development")

    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise ImportError(
            "Couldn't import dotenv. Did you forget to activate a virtual environment?"
        ) from exc

    basedir = Path(__file__).parent

    envfile = os.environ.get("ENV_FILE_PATH", f"{basedir}/.env")
    load_dotenv(envfile, override=True)

    # Powered by "django-configurations", see https://django-configurations.readthedocs.io/en/2.1/
    from configurations.management import execute_from_command_line

    execute_from_command_line(sys.argv)
