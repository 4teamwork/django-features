__all__ = ["get_custom_field_model", "get_custom_value_model"]


from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.value import AbstractBaseCustomValue


def get_custom_field_model() -> AbstractBaseCustomField:
    """
    Return the CustomField model that is active in this project.
    """
    if settings.CUSTOM_FIELD_MODEL is None:
        raise ImproperlyConfigured(
            "CUSTOM_FIELD_MODEL and CUSTOM_FIELD_VALUE_MODEL must be defined in settings to use the custom fields app."
        )

    try:
        return django_apps.get_model(settings.CUSTOM_FIELD_MODEL, require_ready=False)  # type: ignore[unused-ignore]
    except ValueError:
        raise ImproperlyConfigured(
            "CUSTOM_FIELD_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CUSTOM_FIELD_MODEL refers to model '%s' that has not been installed"
            % settings.CUSTOM_FIELD_MODEL
        )


def get_custom_value_model() -> AbstractBaseCustomValue:
    """
    Return the CustomValue model that is active in this project.
    """
    if settings.CUSTOM_FIELD_VALUE_MODEL is None:
        raise ImproperlyConfigured(
            "CUSTOM_FIELD_MODEL and CUSTOM_FIELD_VALUE_MODEL must be defined in settings to use the custom fields app."
        )

    try:
        return django_apps.get_model(  # type: ignore[unused-ignore]
            settings.CUSTOM_FIELD_VALUE_MODEL, require_ready=False
        )
    except ValueError:
        raise ImproperlyConfigured(
            "CUSTOM_FIELD_VALUE_MODEL must be of the form 'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CUSTOM_FIELD_VALUE_MODEL refers to model '%s' that has not been installed"
            % settings.CUSTOM_FIELD_VALUE_MODEL
        )
