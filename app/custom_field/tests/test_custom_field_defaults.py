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


@pytest.mark.parametrize(
    "field_type,default,multiple,edited",
    [
        ("BOOLEAN", False, False, True),
        ("INTEGER", 0, False, 17),
        ("CHAR", "", False, "edited"),
        ("CHAR", [], True, ["edited"]),
        ("DATE", "2026-01-02", False, "2025-01-01"),
    ],
)
def test_defaults_initialize_creates_and_full_updates_preserve_omission(
    field_type: str,
    default: Any,
    multiple: bool,
    edited: Any,
) -> None:
    field = CustomFieldFactory(
        identifier="custom", field_type=field_type, default=default, multiple=multiple
    )
    data = {"firstname": "Default", "lastname": "Person"}
    serializer = PersonSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    person = serializer.save()
    value = person.custom_values.get(field=field)
    assert value.value == default
    value.value = edited
    value.save()
    serializer = PersonSerializer(person, data=data)
    assert serializer.is_valid(), serializer.errors
    assert "custom" not in serializer.validated_data
    serializer.save()
    value.refresh_from_db()
    assert value.value == edited
    assert person.custom_values.get(field=field).pk == value.pk

    serializer = PersonSerializer(person, data={**data, "custom": default})
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    value.refresh_from_db()
    assert value.value == default
    serializer = PersonSerializer(person, data={**data, "custom": None})
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert not person.custom_values.exists()


def test_bound_nested_serializer_uses_its_own_instance() -> None:
    from rest_framework import serializers

    field = CustomFieldFactory(identifier="custom", field_type="BOOLEAN", default=False)
    person = PersonFactory()
    person.custom_values.add(CustomValueFactory(field=field, value=True))

    class Envelope(serializers.Serializer):
        person = PersonSerializer()

    data = {"person": {"firstname": "Nested", "lastname": "Person"}}
    envelope = Envelope(data=data)
    envelope.fields["person"].instance = person
    assert envelope.is_valid(), envelope.errors
    assert "custom" not in envelope.validated_data["person"]
    envelope.fields["person"].update(person, envelope.validated_data["person"])
    assert person.custom_values.get(field=field).value is True
    # A new nested object on an existing envelope is still a create.
    envelope = Envelope(instance=object(), data=data)
    assert envelope.is_valid(), envelope.errors
    assert envelope.validated_data["person"]["custom"] is False


def test_reused_child_checks_current_instance_for_each_row() -> None:
    scalar = CustomFieldFactory(identifier="notes", multiple=True, default=["default"])
    choice = CustomFieldFactory(identifier="choice", choice_field=True)
    selected = CustomValueFactory(field=choice)
    choice.default = selected.pk
    choice.save()
    child = PersonSerializer()
    data = {"firstname": "Row", "lastname": "Person"}
    existing = PersonFactory()
    for instance in (existing, None, existing, None):
        child.instance = instance
        validated = child.run_validation(data)
        if instance is None:
            assert validated["notes"] == ["default"]
            assert validated["choice"] == selected
            created = child.create(validated)
            assert created.custom_values.get(field=scalar).value == ["default"]
        else:
            assert "notes" not in validated
            assert "choice" not in validated


def test_required_defaults_still_require_input_on_full_update() -> None:
    field = CustomFieldFactory(
        identifier="required", required=True, field_type="BOOLEAN", default=False
    )
    person = PersonFactory()
    person.custom_values.add(CustomValueFactory(field=field, value=True))
    serializer = PersonSerializer(person, data={"firstname": "Updated"})
    assert not serializer.is_valid()
    assert serializer.errors["required"][0].code == "required"
    serializer = PersonSerializer(person, data={"firstname": "Updated"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert person.custom_values.get(field=field).value is True


def test_create_defaults_keep_bulk_storage_and_bounded_field_queries(
    django_assert_num_queries: Any,
) -> None:
    from unittest.mock import patch

    from app.custom_field.models import CustomValue

    for index in range(6):
        CustomFieldFactory(
            identifier=f"custom_{index}", field_type="CHAR", multiple=True, default=[]
        )
    serializer = PersonSerializer(data={"firstname": "Bulk", "lastname": "Person"})
    with django_assert_num_queries(1):
        assert serializer.is_valid(), serializer.errors
    with patch.object(
        CustomValue.objects, "bulk_create", wraps=CustomValue.objects.bulk_create
    ) as bulk:
        person = serializer.save()
    assert bulk.call_count == 1
    assert len(bulk.call_args.args[0]) == 6
    assert person.custom_values.count() == 6


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


@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize("many", [False, True])
def test_mapping_choice_defaults_are_canonical_ids_on_create_only(
    multiple: bool, many: bool, django_assert_num_queries: Any
) -> None:
    field = CustomFieldFactory(
        identifier="choice", choice_field=True, multiple=multiple
    )
    intended = CustomValueFactory(field=field, value="canonical")
    decoy = CustomValueFactory(field=field, value=intended.pk)
    field.default = [str(intended.pk)] if multiple else str(intended.pk)
    field.save()
    data = {"firstname": "Default", "lastname": "Person"}
    serializer = ChoiceDefaultMappingSerializer(
        data=[data] * 8 if many else data, many=many
    )
    with django_assert_num_queries(2):
        assert serializer.is_valid(), serializer.errors
    if multiple and many:
        first, second = [row["choice"] for row in serializer.validated_data[:2]]
        assert isinstance(first, list)
        assert isinstance(second, list)
        assert first is not second
        assert first == second == [intended]
    created = serializer.save()
    person = created[0] if many else created
    assert list(person.custom_values.all()) == [intended]

    # Explicit client input continues to match the configured value key.
    serializer = ChoiceDefaultMappingSerializer(
        data={**data, "choice": [intended.pk] if multiple else intended.pk}
    )
    assert serializer.is_valid(), serializer.errors
    value = serializer.validated_data["choice"]
    assert (list(value) if multiple else value) == ([decoy] if multiple else decoy)

    person.custom_values.set([decoy])
    serializer = ChoiceDefaultMappingSerializer(person, data=data)
    assert serializer.is_valid(), serializer.errors
    assert "choice" not in serializer.validated_data
    serializer.save()
    assert list(person.custom_values.all()) == [decoy]

    # PATCH omission must not apply the configured ID or the client's value key.
    person.custom_values.set([decoy])
    serializer = ChoiceDefaultMappingSerializer(
        person, data={"firstname": "Patched"}, partial=True
    )
    assert serializer.is_valid(), serializer.errors
    assert "choice" not in serializer.validated_data
    serializer.save()
    assert list(person.custom_values.all()) == [decoy]


def test_mutable_defaults_are_fresh_for_reused_fields_and_many_serializer() -> None:
    field = CustomFieldFactory(
        identifier="notes", field_type="CHAR", multiple=True, default=["default"]
    )
    validator = field.serializer_field
    first = validator.run_validation(empty)
    second = validator.run_validation(empty)
    first.append("mutated")
    assert second == ["default"]
    assert field.default == ["default"]

    serializer = PersonSerializer(
        data=[
            {"firstname": "First", "lastname": "Person"},
            {"firstname": "Second", "lastname": "Person"},
        ],
        many=True,
    )
    assert serializer.is_valid(), serializer.errors
    values = serializer.validated_data
    assert values[0]["notes"] is not values[1]["notes"]
    values[0]["notes"].append("first-only")
    people = serializer.save()
    assert people[0].custom_values.get(field=field).value == ["default", "first-only"]
    assert people[1].custom_values.get(field=field).value == ["default"]
    field.refresh_from_db()
    assert field.default == ["default"]


def test_date_default_persistence_and_partial_scalar_updates() -> None:
    day = CustomFieldFactory(identifier="day", field_type="DATE", default="2026-01-02")
    notes = CustomFieldFactory(
        identifier="notes", field_type="CHAR", multiple=True, default=["default"]
    )
    serializer = PersonSerializer(data={"firstname": "Default", "lastname": "Person"})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["day"] == date(2026, 1, 2)
    person = serializer.save()
    assert person.custom_values.get(field=day).value == "2026-01-02"

    person.custom_values.filter(field=day).update(value="2025-03-04")
    person.custom_values.filter(field=notes).update(value=["manual"])
    serializer = PersonSerializer(person, data={"firstname": "Patched"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert "notes" not in serializer.validated_data
    assert "day" not in serializer.validated_data
    serializer.save()
    assert person.custom_values.get(field=day).value == "2025-03-04"
    assert person.custom_values.get(field=notes).value == ["manual"]

    serializer = PersonSerializer(person, data={"notes": []}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert person.custom_values.get(field=notes).value == []
    assert person.custom_values.get(field=day).value == "2025-03-04"


@pytest.mark.parametrize("default", ["invalid-date", [], {}, 0, False])
def test_invalid_date_defaults_are_configuration_errors(default: Any) -> None:
    field = CustomFieldFactory(field_type="DATE", default=default)
    with pytest.raises(ValidationError) as caught:
        field.full_clean()
    assert "default" in caught.value.message_dict


def test_partial_choice_null_clears_without_applying_default() -> None:
    field = CustomFieldFactory(identifier="choice", choice_field=True)
    choice = CustomValueFactory(field=field)
    field.default = choice.pk
    field.save()
    person = PersonFactory()
    person.custom_values.add(choice)
    serializer = PersonSerializer(person, data={"choice": None}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert not person.custom_values.exists()


@pytest.mark.parametrize(
    "field_type,default,multiple,existing",
    [
        ("BOOLEAN", "ja", False, False),
        ("DATE", "private-invalid-date", False, "2026-01-02"),
        ("INTEGER", ["private-invalid-int"], True, [0]),
    ],
)
def test_invalid_scalar_defaults_skip_omission_but_preserve_explicit_validation(
    field_type: str, default: Any, multiple: bool, existing: Any, caplog: Any
) -> None:
    field = CustomFieldFactory(
        identifier="custom",
        field_type=field_type,
        default=default,
        multiple=multiple,
        allow_null=False,
    )
    data = {"firstname": "Default", "lastname": "Person"}
    serializer = PersonSerializer(data=[data] * 8, many=True)
    assert serializer.is_valid(), serializer.errors
    assert all("custom" not in row for row in serializer.validated_data)
    assert len(caplog.records) == 1
    assert caplog.records[0].name == "django_features.custom_fields"
    assert caplog.records[0].exc_info is None
    assert caplog.records[0].custom_field_model == field._meta.label_lower
    assert caplog.records[0].custom_field_pk == field.pk
    assert caplog.records[0].code == "invalid_custom_field_default"
    assert caplog.messages == ["Ignoring invalid custom field default configuration."]
    people = serializer.save()
    assert all(not person.custom_values.exists() for person in people)
    caplog.clear()
    assert len(PersonSerializer(Person.objects.all(), many=True).data) == 8
    assert caplog.messages == ["Ignoring invalid custom field default configuration."]
    person = people[0]
    person.custom_values.add(CustomValueFactory(field=field, value=existing))
    for partial in (False, True):
        serializer = PersonSerializer(person, data=data, partial=partial)
        assert serializer.is_valid(), serializer.errors
        assert "custom" not in serializer.validated_data
        serializer.save()
        assert person.custom_values.get(field=field).value == existing
    serializer = PersonSerializer(data={**data, "custom": default})
    assert not serializer.is_valid()
    assert "custom" in serializer.errors
    # Re-fetching exercises annotated custom values used by runtime reads.
    assert PersonSerializer(Person.objects.get(pk=person.pk)).data["custom"] == existing
    assert PersonSerializer(Person.objects.get(pk=people[1].pk)).data["custom"] is None


@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize(
    "invalid_kind", ["deleted", "foreign", "malformed", "wrong_shape", "duplicate"]
)
@pytest.mark.parametrize(
    "serializer_class", [PersonSerializer, ChoiceDefaultMappingSerializer]
)
def test_invalid_choice_defaults_are_omitted(
    multiple: bool, invalid_kind: str, serializer_class: Any, caplog: Any
) -> None:
    field = CustomFieldFactory(
        identifier="choice", choice_field=True, multiple=multiple, allow_null=False
    )
    survivor = CustomValueFactory(field=field, value="survivor")
    if invalid_kind == "deleted":
        deleted = CustomValueFactory(field=field)
        value = deleted.pk
        deleted.delete()
    elif invalid_kind == "foreign":
        value = CustomValueFactory().pk
    else:
        value = {"private-invalid": "payload"}
    field.default = [value] if multiple else value
    if invalid_kind == "wrong_shape":
        field.default = survivor.pk if multiple else [survivor.pk]
    elif invalid_kind == "duplicate":
        field.default = [survivor.pk, str(survivor.pk)]
    field.save()
    with pytest.raises(ValidationError) as caught:
        field.clean()
    assert "default" in caught.value.message_dict
    data = {"firstname": "Default", "lastname": "Person"}
    serializer = serializer_class(data=[data] * 8, many=True)
    assert serializer.is_valid(), serializer.errors
    assert all("choice" not in row for row in serializer.validated_data)
    assert caplog.messages == ["Ignoring invalid custom field default configuration."]
    people = serializer.save()
    assert all(not person.custom_values.exists() for person in people)
    person = people[0]
    person.custom_values.add(survivor)
    for partial in (False, True):
        serializer = serializer_class(person, data=data, partial=partial)
        assert serializer.is_valid(), serializer.errors
        assert "choice" not in serializer.validated_data
        serializer.save()
        assert list(person.custom_values.all()) == [survivor]
    serializer = serializer_class(data={**data, "choice": field.default})
    assert not serializer.is_valid()
    assert "choice" in serializer.errors
    assert PersonSerializer(Person.objects.get(pk=people[1].pk)).data["choice"] == (
        [] if multiple else None
    )


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
@pytest.mark.parametrize(
    "serializer_class", [PersonSerializer, ChoiceDefaultMappingSerializer]
)
def test_valid_explicit_choice_persists_despite_invalid_default(
    multiple: bool, serializer_class: Any
) -> None:
    field = CustomFieldFactory(
        identifier="choice",
        choice_field=True,
        multiple=multiple,
        default=[999999] if multiple else 999999,
    )
    choice = CustomValueFactory(field=field, value="explicit-token")
    token = choice.pk if serializer_class is PersonSerializer else choice.value
    serializer = serializer_class(
        data={
            "firstname": "Explicit",
            "lastname": "Person",
            "choice": [token] if multiple else token,
        }
    )
    assert serializer.is_valid(), serializer.errors
    assert list(serializer.save().custom_values.all()) == [choice]


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
