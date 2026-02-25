__all__ = [
    "get_custom_field_model",
    "get_custom_value_model",
    "clear_custom_field_model_cache",
]


from functools import lru_cache

from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.value import AbstractBaseCustomValue


@lru_cache(maxsize=1)
def get_custom_field_model() -> type[AbstractBaseCustomField]:
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


@lru_cache(maxsize=1)
def get_custom_value_model() -> type[AbstractBaseCustomValue]:
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


def clear_custom_field_model_cache() -> None:
    """
    Clear cached model lookups for custom fields.
    """
    get_custom_field_model.cache_clear()
    get_custom_value_model.cache_clear()
