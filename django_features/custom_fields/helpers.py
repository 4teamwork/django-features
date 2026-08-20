__all__ = [
    "clear_custom_field_model_cache",
    "get_custom_field_model",
    "get_reserved_custom_field_identifiers",
    "get_custom_value_model",
    "validate_custom_field_identifiers",
]


from collections.abc import Iterable
from functools import lru_cache

from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.value import AbstractBaseCustomValue


# These attributes are installed on CustomFieldBaseModel instances instead of on
# the model class, so ``dir(model)`` cannot discover them.  A custom-field value
# must never be injected into any of them through an annotation or ``__dict__``.
CUSTOM_FIELD_INSTANCE_RESERVED_IDENTIFIERS = frozenset(
    {
        "_custom_values_to_delete",
        "_custom_values_to_remove",
        "_custom_values_to_save",
        "_prefetched_objects_cache",
        "_state",
        "custom_field_keys",
        "handle_custom_values",
    }
)


def get_reserved_custom_field_identifiers(
    model: type[models.Model],
) -> set[str]:
    """Return model and framework-instance names unavailable to custom fields."""
    reserved = set(CUSTOM_FIELD_INSTANCE_RESERVED_IDENTIFIERS)
    for model_class in model.__mro__:
        reserved.update(
            model_class.__dict__.get("_custom_field_reserved_identifiers", ())
        )
    reserved.update(dir(model))
    for model_field in model._meta.get_fields():
        reserved.add(model_field.name)
        attname = getattr(model_field, "attname", None)
        if attname:
            reserved.add(attname)
    return reserved


def validate_custom_field_identifiers(
    model: type[models.Model],
    identifiers: Iterable[str],
    *,
    extra_reserved: Iterable[str] = (),
) -> None:
    """Reject identifiers that could overwrite model or serializer state."""
    reserved = get_reserved_custom_field_identifiers(model)
    reserved.update(extra_reserved)
    collisions = set(identifiers) & reserved
    if not collisions:
        return
    formatted = ", ".join(repr(identifier) for identifier in sorted(collisions))
    raise ImproperlyConfigured(
        f"Custom field identifier(s) {formatted} for {model._meta.label} "
        "conflict with reserved model or serializer attributes."
    )


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
