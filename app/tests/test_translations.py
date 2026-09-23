import pytest
from django.test import override_settings
from django.utils.translation import gettext
from django.utils.translation import override


@pytest.mark.parametrize(
    "app_name, message, english, french",
    [
        (
            "django_features.custom_fields",
            "Feldtyp",
            "Field type",
            "Type de champ",
        ),
        (
            "django_features.custom_fields",
            "Externer Schlüssel",
            "External key",
            "Clé externe",
        ),
        (
            "django_features.custom_fields",
            "Eine Option darf nur einmal ausgewählt werden.",
            "A choice may only be selected once.",
            "Une option ne peut être sélectionnée qu'une seule fois.",
        ),
        (
            "django_features.system_message",
            "Systemmeldung",
            "system message",
            "Message système",
        ),
        (
            "django_features",
            "Inkorrekter Typ.",
            "Incorrect type.",
            "Type incorrect.",
        ),
    ],
)
def test_app_translations_without_locale_paths(
    app_name: str, message: str, english: str, french: str
) -> None:
    with override_settings(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            app_name,
        ],
        LOCALE_PATHS=[],
    ):
        for language, expected in (("de", message), ("en", english), ("fr", french)):
            with override(language):
                assert gettext(message) == expected
