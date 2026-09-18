from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty

from app.custom_field.models import CustomField
from app.custom_field.models import CustomValue
from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.models import Person
from app.serializers.person import PersonSerializer
from django_features.custom_fields.fields import ChoiceIdField
from django_features.custom_fields.serializers import CustomFieldSerializer


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "multiple,data,code",
    [
        (True, 1, "shape"),
        (True, "1", "shape"),
        (True, {"id": 1}, "shape"),
        (False, [1], "shape"),
        (False, True, "invalid"),
        (False, 1.5, "invalid"),
        (False, {}, "invalid"),
        (False, {"id": {}}, "invalid"),
        (False, {"id": "bad"}, "invalid"),
        (True, [{"id": 1}, {}], "invalid"),
        (True, [{"id": 1}, {"id": "1"}], "duplicate"),
        (True, [1, "1"], "duplicate"),
        (True, [None], "invalid"),
        (True, [[1]], "invalid"),
        (True, [{"id": 999999}], "missing"),
    ],
)
def test_invalid_shapes(multiple: bool, data: Any, code: str) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    with pytest.raises(ValidationError) as error:
        field.serializer_field.run_validation(data)
    assert error.value.get_codes() == [code]
    assert CustomValue.objects.count() == 0


@pytest.mark.parametrize("multiple", [False, True])
def test_null_required_and_empty(multiple: bool) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    assert field.serializer_field.run_validation(None) is None
    field.allow_null = False
    with pytest.raises(ValidationError) as error:
        field.serializer_field.run_validation(None)
    assert error.value.get_codes() == ["null"]
    field.required = True
    with pytest.raises(ValidationError) as error:
        field.serializer_field.run_validation(empty)
    assert error.value.get_codes() == ["required"]
    if multiple:
        assert field.serializer_field.run_validation([]) == []
        field.allow_blank = False
        with pytest.raises(ValidationError) as error:
            field.serializer_field.run_validation([])
        assert error.value.get_codes() == ["empty"]


@pytest.mark.parametrize("supplied_order", [None, "forward", "reverse"])
@pytest.mark.parametrize("use_default", [False, True])
def test_id_forms_scoping_order_and_supplied_collections(
    supplied_order: str | None,
    use_default: bool,
    django_assert_num_queries: Any,
) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=True)
    second = CustomValueFactory(field=field, order=2)
    first = CustomValueFactory(field=field, order=1)
    CustomValueFactory(field=field, order=3)
    foreign = CustomValueFactory(
        field=CustomFieldFactory(identifier="foreign", choice_field=True)
    )
    expected = [second, first] if supplied_order == "reverse" else [first, second]
    supplied = expected.copy() if supplied_order is not None else None
    selection = [{"id": str(expected[1].id)}, expected[0].id]
    serializer = ChoiceIdField(field, choices=supplied, default=selection)
    data = empty if use_default else selection
    with django_assert_num_queries(1 if supplied is None else 0):
        result = serializer.run_validation(data)
    with django_assert_num_queries(0):
        assert isinstance(result, list)
        assert result == expected
        assert len(result) == 2
        assert serializer.to_representation(result)[0] == {
            "id": expected[0].id,
            "label": expected[0].label,
            "value": expected[0].value,
        }
        result.clear()
        repeated = serializer.run_validation(data)
        assert repeated is not result
        assert repeated == expected
        assert supplied is None or supplied == expected
        with pytest.raises(ValidationError) as error:
            serializer.run_validation([foreign.id])
        assert error.value.get_codes() == ["missing"]
    field.multiple = False
    assert ChoiceIdField(field).run_validation({"id": str(first.id)}) == first


@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize("value", ["token", None, False, 0, ""])
def test_configured_keys_and_id_fallback(multiple: bool, value: Any) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    choice = CustomValueFactory(field=field, value=value)
    serializer = ChoiceIdField(field, unique_field="value")
    inputs = [
        {"value": value},
        {"id": value},
        {"id": "other", "value": value, "label": "Display metadata"},
    ]
    if value is not None:
        inputs.append(value)
    for data in inputs:
        result = serializer.run_validation([data] if multiple else data)
        assert (list(result) if multiple else result) == (
            [choice] if multiple else choice
        )
    with pytest.raises(ValueError, match="Invalid unique_field"):
        ChoiceIdField(field, unique_field="unknown")


@pytest.mark.parametrize("multiple", [False, True])
def test_ambiguous_choices_and_type_aware_values(multiple: bool) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    one = CustomValueFactory(field=field, value=1)
    boolean = CustomValueFactory(field=field, value=True)
    string = CustomValueFactory(field=field, value="1")
    serializer = ChoiceIdField(field, unique_field="value")
    for value, choice in [(1, one), (True, boolean), ("1", string)]:
        result = serializer.run_validation([value] if multiple else value)
        assert (list(result) if multiple else result) == (
            [choice] if multiple else choice
        )
    if multiple:
        assert list(serializer.run_validation([1, True, "1"])) == [one, boolean, string]
    CustomValueFactory(field=field, value=1)
    with pytest.raises(ValidationError) as error:
        ChoiceIdField(field, unique_field="value").run_validation(
            [1] if multiple else 1
        )
    assert error.value.get_codes() == ["ambiguous"]


@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize("unique_field", ["value", "label"])
@pytest.mark.parametrize("value", [{"nested": [1]}, [1, "one"]])
def test_structured_lookup_values_are_invalid(
    multiple: bool, unique_field: str, value: Any
) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    serializer = ChoiceIdField(field, unique_field=unique_field)
    data = {unique_field: value, "id": "valid"}
    CustomValueFactory(field=field, **{unique_field: "valid"})
    with pytest.raises(ValidationError) as error:
        serializer.run_validation([data] if multiple else data)
    assert error.value.get_codes() == ["invalid"]


def test_configured_concrete_field_preserves_database_conversion() -> None:
    field = CustomFieldFactory(choice_field=True)
    choice = CustomValueFactory(field=field, order=10)
    assert ChoiceIdField(field, unique_field="order").run_validation("10") == choice


def test_nullable_labels_do_not_block_other_lookups() -> None:
    field = CustomFieldFactory(choice_field=True)
    CustomValueFactory(field=field, label=None)
    choice = CustomValueFactory(field=field, label="Selected")
    assert (
        ChoiceIdField(field, unique_field="label").run_validation("Selected") == choice
    )


@pytest.mark.parametrize("multiple", [False, True])
def test_invalid_supplied_collection_never_leaves_a_partial_index(
    multiple: bool,
) -> None:
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    own = CustomValueFactory(field=field)
    foreign = CustomValueFactory(
        field=CustomFieldFactory(identifier="foreign", choice_field=True)
    )
    serializer = ChoiceIdField(field, choices=[own, foreign])
    for _ in range(2):
        with pytest.raises(ValidationError) as error:
            serializer.run_validation([own.id] if multiple else own.id)
        assert error.value.get_codes() == ["invalid"]


@pytest.mark.parametrize("unique_field", ["id", "pk"])
def test_configured_primary_key_and_strict_integer_ids(unique_field: str) -> None:
    field = CustomFieldFactory(choice_field=True)
    choice = CustomValueFactory(field=field)
    validator = ChoiceIdField(field, unique_field=unique_field)
    for data in [
        choice.pk,
        str(choice.pk),
        {unique_field: choice.pk},
        {"id": choice.pk},
    ]:
        assert validator.run_validation(data) == choice
    for data in [True, False, float(choice.pk), {unique_field: True}]:
        with pytest.raises(ValidationError) as error:
            validator.run_validation(data)
        assert error.value.get_codes() == ["invalid"]
    if unique_field == "id":
        with pytest.raises(ValidationError) as error:
            validator.run_validation({"pk": choice.pk})
        assert error.value.get_codes() == ["invalid"]


def test_concrete_datetime_lookup_accepts_native_values() -> None:
    field = CustomFieldFactory(choice_field=True)
    choice = CustomValueFactory(field=field)
    validator = ChoiceIdField(field, unique_field="created")
    assert validator.run_validation(choice.created) == choice
    assert validator.run_validation({"created": choice.created}) == choice
    assert validator.run_validation(choice.created.isoformat()) == choice
