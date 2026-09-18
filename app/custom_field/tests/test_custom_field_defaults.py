from datetime import date
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from rest_framework.fields import empty

from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.models import Person
from app.serializers.person import PersonSerializer
from app.tests.factories import PersonFactory
from django_features.serializers import MappingSerializer


pytestmark = pytest.mark.django_db


class ChoiceDefaultMappingSerializer(MappingSerializer):
    _mapping = {
        "app.person": {
            "firstname": "firstname",
            "lastname": "lastname",
            "choice": "choice",
        }
    }

    class Meta:
        model = Person
        fields = "__all__"


@pytest.mark.parametrize("default", ["invalid-date", [], {}, 0, False])
def test_invalid_date_defaults_are_configuration_errors(default: Any) -> None:
    field = CustomFieldFactory(field_type="DATE", default=default)
    with pytest.raises(ValidationError) as caught:
        field.full_clean()
    assert "default" in caught.value.message_dict


def test_required_field_with_invalid_default_stays_required() -> None:
    field = CustomFieldFactory(
        identifier="required", field_type="BOOLEAN", default="ja", required=True
    )
    with pytest.raises(ValidationError):
        field.clean()
    serializer = PersonSerializer(data={"firstname": "Default", "lastname": "Person"})
    assert not serializer.is_valid()
    assert serializer.errors["required"][0].code == "required"


def test_admin_form_rejects_invalid_defaults_on_default_field() -> None:
    from django.contrib import admin
    from django.forms.models import model_to_dict
    from django.test import RequestFactory

    from app.custom_field.models import CustomField

    field = CustomFieldFactory(field_type="BOOLEAN", default="ja")
    form_class = admin.site._registry[CustomField].get_form(
        RequestFactory().get("/"), field
    )
    data = model_to_dict(field)
    data["default"] = '"ja"'
    form = form_class(data=data, instance=field)
    assert not form.is_valid()
    assert "default" in form.errors


@pytest.mark.parametrize("multiple", [False, True])
def test_pending_choices_do_not_invalidate_persisted_default(multiple: bool) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    existing = CustomValueFactory(field=field)
    pending = CustomValueFactory.build(field=field)
    field.default = [existing.pk] if multiple else existing.pk
    value = field.validate_default(choices=[existing, pending])
    assert (list(value) if multiple else value) == (
        [existing] if multiple else existing
    )


def test_unknown_scalar_type_is_a_configuration_error() -> None:
    field = CustomFieldFactory(field_type="UNKNOWN", default="configured")
    with pytest.raises(ValidationError) as caught:
        field.clean()
    assert set(caught.value.message_dict) == {"field_type"}
    # Runtime safety is limited to invalid defaults, not unrelated schema failures.
    with pytest.raises(ValueError, match="Unknown field type"):
        field.serializer_field


@pytest.mark.parametrize(
    "language,default_error,type_error",
    [
        (
            "de",
            "Der Standardwert entspricht nicht den Feldregeln.",
            "Wählen Sie einen unterstützten Feldtyp.",
        ),
        (
            "fr",
            "La valeur par défaut ne respecte pas les règles du champ.",
            "Sélectionnez un type de champ pris en charge.",
        ),
    ],
)
def test_configuration_validation_is_localized(
    language: str, default_error: str, type_error: str
) -> None:
    from django.utils.translation import override

    field = CustomFieldFactory(field_type="BOOLEAN", default="ja")
    with override(language):
        with pytest.raises(ValidationError) as caught:
            field.clean()
        assert caught.value.message_dict["default"] == [default_error]
        field.field_type = "UNKNOWN"
        with pytest.raises(ValidationError) as caught:
            field.clean()
        assert caught.value.message_dict["field_type"] == [type_error]


def test_default_validator_does_not_validate_unrelated_type_without_default() -> None:
    field = CustomFieldFactory(field_type="UNKNOWN", default=None)
    assert field.validate_default() is None
    field.choice_field = True
    field.default = 123
    assert field.validate_default(validate_choices=False) is None
