from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.db import transaction
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


@pytest.mark.parametrize(
    "field_type,default,multiple",
    [
        ("BOOLEAN", False, False),
        ("INTEGER", 0, False),
        ("CHAR", "", False),
        ("CHAR", [], True),
        ("CHAR", [""], True),
        ("INTEGER", [0], True),
    ],
)
def test_falsy_defaults(field_type: str, default: Any, multiple: bool) -> None:
    field = CustomFieldFactory(
        field_type=field_type, default=default, multiple=multiple
    )
    serializer = field.serializer_field
    assert serializer.run_validation(empty) == default
    assert serializer.run_validation(default) == default
    assert serializer.run_validation(None) is None
    assert CustomFieldSerializer(field).data["default"] == default


@pytest.mark.parametrize(
    "field_type,default,multiple",
    [
        ("INTEGER", [], False),
        ("CHAR", "text", True),
        ("CHAR", [], True),
    ],
)
def test_invalid_default_configuration(
    field_type: str, default: Any, multiple: bool
) -> None:
    field = CustomFieldFactory(
        field_type=field_type, default=default, multiple=multiple, allow_blank=False
    )
    from django.core.exceptions import ValidationError as ConfigurationError

    with pytest.raises(ConfigurationError) as caught:
        field.clean()
    assert "default" in caught.value.message_dict


def test_choice_defaults_are_validated_objects(django_assert_num_queries: Any) -> None:
    field = CustomFieldFactory(choice_field=True)
    choice = CustomValueFactory(field=field)
    field.default = choice.id
    assert field.serializer_field.run_validation(empty) == choice
    field.multiple = True
    field.default = []
    assert list(field.serializer_field.run_validation(empty)) == []
    field.default = [choice.id]
    assert list(field.serializer_field.run_validation(empty)) == [choice]
    validator = ChoiceIdField(
        field, unique_field="value", choices=[choice], default=field.default
    )
    pk_field = CustomValue._meta.pk
    with django_assert_num_queries(0), patch.object(
        pk_field, "to_python", wraps=pk_field.to_python
    ) as normalize_pk:
        assert list(validator.run_validation([choice.value])) == [choice]
        assert list(validator.run_validation(empty)) == [choice]
        assert list(validator.run_validation([choice.value])) == [choice]
        assert list(validator.run_validation(empty)) == [choice]
    # One catalog key plus the two default IDs; the PK index is reused.
    assert normalize_pk.call_count == 3


@pytest.mark.parametrize("number", [1, 12])
def test_prefetched_metadata_validation_budget(
    number: int, django_assert_num_queries: Any
) -> None:
    ContentType.objects.get_for_model(Person)
    for index in range(number):
        field = CustomFieldFactory(
            identifier=f"choice_{index}", choice_field=True, multiple=True
        )
        for item in range(4):
            CustomValueFactory(field=field, value=str(item))
    with django_assert_num_queries(2):
        fields = list(CustomField.objects.for_model(Person).with_choices())
        assert len(CustomFieldSerializer(fields, many=True).data) == number
        serializer = PersonSerializer(custom_fields=fields)
        for field in fields:
            choices = list(field.choices)
            assert (
                len(
                    serializer.fields[field.identifier].run_validation(
                        [choice.id for choice in choices]
                    )
                )
                == 4
            )
    with django_assert_num_queries(1):
        assert len(PersonSerializer().fields) >= number


@pytest.mark.parametrize("number", [0, 1, 12])
@pytest.mark.parametrize("shape", ["single", "many", "nested", "nested_many"])
@pytest.mark.parametrize("partial", [False, True])
def test_input_loads_only_used_choice_catalogs(
    number: int, shape: str, partial: bool, django_assert_num_queries: Any
) -> None:
    ContentType.objects.get_for_model(Person)
    unused = CustomFieldFactory(identifier="unused_choice", choice_field=True)
    CustomValueFactory.create_batch(40, field=unused)
    data: dict[str, Any] = {"firstname": "Example"}
    selected = {}
    for index in range(number):
        field = CustomFieldFactory(identifier=f"choice_{index}", choice_field=True)
        choice = CustomValueFactory(field=field)
        data[field.identifier] = choice.pk
        selected[field.identifier] = choice
    many = shape in {"many", "nested_many"}
    payload = [data, data] if many else data
    # One metadata query and one catalog query per used field, reused across items.
    with django_assert_num_queries(1 + number) as queries:
        if shape.startswith("nested"):

            class ParentSerializer(serializers.Serializer):
                person = PersonSerializer(many=many)

            serializer = ParentSerializer(data={"person": payload}, partial=partial)
        else:
            serializer = PersonSerializer(data=payload, many=many, partial=partial)
        assert serializer.is_valid(), serializer.errors
    if number == 0:
        assert CustomValue._meta.db_table not in queries.captured_queries[0]["sql"]
    validated = serializer.validated_data
    if shape.startswith("nested"):
        validated = validated["person"]
    for item in validated if many else [validated]:
        assert unused.identifier not in item
        assert all(item[key] == choice for key, choice in selected.items())


@pytest.mark.parametrize("shape", ["single", "many", "nested", "nested_many"])
@pytest.mark.parametrize("multiple", [False, True])
def test_reads_do_not_load_unused_choice_catalogs(
    shape: str, multiple: bool, django_assert_num_queries: Any
) -> None:
    ContentType.objects.get_for_model(Person)
    field = CustomFieldFactory(choice_field=True, multiple=multiple)
    CustomValueFactory.create_batch(40, field=field, value="unused")
    people = []
    expected_people = []
    for index in range(2):
        selected = CustomValueFactory(field=field, value=f"selected-{index}")
        person = Person.objects.create(firstname=f"Example {index}")
        person.custom_values.add(selected)
        # Fetch selected model values separately from serializer definitions
        # and the unused choice catalog.
        people.append(Person.objects.get(pk=person.pk))
        choice = {"id": selected.pk, "label": selected.label, "value": selected.value}
        expected_people.append(
            {
                "firstname": person.firstname,
                "lastname": None,
                "email": None,
                field.identifier: [choice] if multiple else choice,
            }
        )
    many = shape in {"many", "nested_many"}
    instance = people if many else people[0]
    expected = expected_people if many else expected_people[0]
    for _ in range(3):
        with django_assert_num_queries(1) as queries:
            if shape.startswith("nested"):

                class ParentSerializer(serializers.Serializer):
                    person = PersonSerializer(many=many)

                serializer = ParentSerializer({"person": instance})
                expected_data = {"person": expected}
            else:
                serializer = PersonSerializer(instance, many=many)
                expected_data = expected
            assert serializer.data == expected_data
        assert CustomValue._meta.db_table not in queries.captured_queries[0]["sql"]


@pytest.mark.parametrize("many", [False, True])
def test_read_only_child_does_not_prefetch_choices_for_write_response(
    many: bool, django_assert_num_queries: Any
) -> None:
    field = CustomFieldFactory(choice_field=True)
    selected = CustomValueFactory(field=field, value="selected")
    CustomValueFactory.create_batch(40, field=field, value="unused")
    person = Person.objects.create(firstname="Example")
    person.custom_values.add(selected)
    person = Person.objects.get(pk=person.pk)

    class ParentSerializer(serializers.Serializer):
        person = PersonSerializer(many=many, read_only=True)

    expected = {
        "firstname": "Example",
        "lastname": None,
        "email": None,
        field.identifier: {
            "id": selected.pk,
            "label": selected.label,
            "value": "selected",
        },
    }
    with django_assert_num_queries(1) as queries:
        serializer = ParentSerializer({"person": [person] if many else person}, data={})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data == {}
        assert serializer.data == {"person": [expected] if many else expected}
    assert CustomValue._meta.db_table not in queries.captured_queries[0]["sql"]


def test_standard_reverse_prefetch_is_reused(django_assert_num_queries: Any) -> None:
    field = CustomFieldFactory(choice_field=True)
    choice = CustomValueFactory(field=field)
    with django_assert_num_queries(2):
        loaded = CustomField.objects.prefetch_related("values").get(pk=field.pk)
        assert loaded.serializer_field.run_validation(choice.id) == choice


def test_external_label_unique_only_within_field_and_nonblank() -> None:
    field = CustomFieldFactory(choice_field=True)
    CustomValueFactory(field=field, external_label="")
    CustomValueFactory(field=field, external_label="")
    CustomValueFactory(field=field, external_label="token")
    other = CustomFieldFactory(identifier="other", choice_field=True)
    CustomValueFactory(field=other, external_label="token")
    with pytest.raises(IntegrityError), transaction.atomic():
        CustomValueFactory(field=field, external_label="token")


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


@pytest.mark.parametrize(
    "code,german,english,french",
    [
        (
            "shape",
            "Für eine Mehrfachauswahl wird eine Liste erwartet, für eine Einfachauswahl ein einzelner Wert.",
            "Expected a list for multiple choices or a scalar for a single choice.",
            "Une liste est attendue pour une sélection multiple, ou une valeur unique pour une sélection simple.",
        ),
        (
            "invalid",
            "Ungültiger Suchwert für die Auswahl.",
            "Invalid choice lookup value.",
            "Valeur de recherche de choix invalide.",
        ),
        (
            "missing",
            "Eine ausgewählte Option existiert nicht in diesem Feld.",
            "A selected choice does not exist in this field.",
            "Une option sélectionnée n'existe pas dans ce champ.",
        ),
        (
            "duplicate",
            "Eine Option darf nur einmal ausgewählt werden.",
            "A choice may only be selected once.",
            "Une option ne peut être sélectionnée qu'une seule fois.",
        ),
        (
            "ambiguous",
            "Mehrere Optionen entsprechen dem Suchwert.",
            "More than one choice matches the lookup value.",
            "Plusieurs options correspondent à la valeur recherchée.",
        ),
        (
            "empty",
            "Diese Liste darf nicht leer sein.",
            "This list may not be empty.",
            "Cette liste ne peut pas être vide.",
        ),
        (
            "blank",
            "Dieses Feld darf nicht leer sein.",
            "This field may not be blank.",
            "Ce champ ne peut pas être vide.",
        ),
        (
            "not_choice",
            "Dieses Feld ist kein Auswahlfeld.",
            "This field is not a choice field.",
            "Ce champ n'est pas un champ de sélection.",
        ),
    ],
)
def test_choice_errors_are_localized(
    code: str, german: str, english: str, french: str
) -> None:
    from django.utils.translation import override

    # Reuse a field created before selecting a language to verify lazy translation.
    validator = ChoiceIdField(CustomFieldFactory(choice_field=True))
    for language, message in (("de", german), ("en", english), ("fr", french)):
        with override(language), pytest.raises(ValidationError) as caught:
            validator.fail(code)
        assert caught.value.get_codes() == [code]
        assert str(caught.value.detail[0]) == message


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


@pytest.mark.parametrize("field_type", ["CHAR", "INTEGER", "BOOLEAN", "DATE"])
def test_scalar_list_child_and_container_rules(field_type: str) -> None:
    field = CustomFieldFactory(
        field_type=field_type, multiple=True, allow_blank=False, allow_null=False
    )
    for data, code in [(None, "null"), ([], "empty"), ("wrong-shape", "not_a_list")]:
        with pytest.raises(ValidationError) as error:
            field.serializer_field.run_validation(data)
        assert error.value.get_codes() == [code]
    with pytest.raises(ValidationError) as error:
        field.serializer_field.run_validation([None])
    assert error.value.get_codes() == {0: ["null"]}


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
