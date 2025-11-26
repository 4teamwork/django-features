from typing import Any

from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_custom_field_model() -> Any:
    """
    Return the CustomField model that is active in this project.
    """
    try:
        return django_apps.get_model(settings.CUSTOM_FIELD_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            f"CUSTOM_FIELD_MODEL must be of the form 'app_label.model_name', given: %s"
            % settings.CUSTOM_FIELD_MODEL
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CUSTOM_FIELD_MODEL refers to model '%s' that has not been installed"
            % settings.CUSTOM_FIELD_MODEL
        )
