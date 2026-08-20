from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from django.db import models
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from app.custom_field.models import CustomField
from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.tests import APITestCase
from app.tests.factories import PersonFactory


class ValueChoicePersonSerializer(TypeAwarePersonSerializer):
    _unique_choice_field = "value"


class PrimaryKeyChoicePersonSerializer(TypeAwarePersonSerializer):
    _unique_choice_field = "pk"


class TextValueValidationTest(APITestCase):
    def test_create_rejects_postgresql_jsonb_incompatible_text(self) -> None:
        invalid_values = (
            ("\x00", "null_characters_not_allowed"),
            ("\ud800", "surrogate_characters_not_allowed"),
        )
        for field_type in (
            CustomField.FIELD_TYPES.CHAR,
            CustomField.FIELD_TYPES.TEXT,
        ):
            field = CustomFieldFactory(
                identifier=f"invalid_{field_type.lower()}",
                field_type=field_type,
            )
            for value, error_code in invalid_values:
                with self.subTest(field_type=field_type, error_code=error_code):
                    serializer = TypeAwarePersonSerializer(
                        data={"firstname": "Invalid text", field.identifier: value}
                    )

                    self.assertFalse(serializer.is_valid())
                    self.assertEqual(
                        serializer.errors[field.identifier][0].code,
                        error_code,
                    )


class MultipleChoiceValidationTest(APITestCase):
    def setUp(self) -> None:
        self.field = CustomFieldFactory(
            identifier="multiple_choices", choice_field=True, multiple=True
        )
        self.first = CustomValueFactory(field=self.field, value="first")
        self.second = CustomValueFactory(field=self.field, value="second")
        self.base_data = {"firstname": "Multiple", "lastname": "Choices"}

    def test_create_accepts_mixed_normalized_payloads(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data={
                **self.base_data,
                self.field.identifier: [str(self.first.id), {"id": self.second.id}],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()
        self.assertSetEqual(
            set(person.custom_values.values_list("id", flat=True)),
            {self.first.id, self.second.id},
        )

    def test_create_accepts_empty_choices_when_blank_is_allowed(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data={**self.base_data, self.field.identifier: []}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertFalse(person.custom_values.filter(field=self.field).exists())

    def test_empty_choices_do_not_query_or_materialize_available_choices(self) -> None:
        serializer_field = self.field.serializer_field

        with self.assertNumQueries(0):
            value = serializer_field.run_validation([])

        self.assertEqual(value, [])

    def test_create_rejects_empty_choices_when_blank_is_not_allowed(self) -> None:
        self.field.allow_blank = False
        self.field.save(update_fields=["allow_blank"])
        serializer = TypeAwarePersonSerializer(
            data={**self.base_data, self.field.identifier: []}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors[self.field.identifier][0].code,
            "empty",
        )

    def test_create_distinguishes_duplicate_malformed_and_nonexistent_choices(
        self,
    ) -> None:
        payloads = {
            "duplicate": [self.first.id, str(self.first.id)],
            "invalid": [self.first.id, {"label": "missing id"}],
            "does_not_exist": [self.first.id, 999_999],
        }
        for error_code, value in payloads.items():
            with self.subTest(error_code=error_code):
                serializer = TypeAwarePersonSerializer(
                    data={**self.base_data, self.field.identifier: value}
                )

                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    serializer.errors[self.field.identifier][0].code,
                    error_code,
                )

    def test_update_rejects_invalid_choices(self) -> None:
        person = PersonFactory()
        for value in (
            [self.first.id, self.first.id],
            [self.first.id, object()],
            [self.first.id, 999_999],
        ):
            with self.subTest(value=value):
                serializer = TypeAwarePersonSerializer(
                    person,
                    data={self.field.identifier: value},
                    partial=True,
                )
                self.assertFalse(serializer.is_valid())
                self.assertIn(self.field.identifier, serializer.errors)

    def test_update_accepts_empty_choices_and_clears_existing_values(self) -> None:
        person = PersonFactory()
        person.custom_values.add(self.first, self.second)
        serializer = TypeAwarePersonSerializer(
            person,
            data={self.field.identifier: []},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertFalse(person.custom_values.filter(field=self.field).exists())

    def test_update_rejects_empty_choices_when_blank_is_not_allowed(self) -> None:
        self.field.allow_blank = False
        self.field.save(update_fields=["allow_blank"])
        person = PersonFactory()
        person.custom_values.add(self.first)
        serializer = TypeAwarePersonSerializer(
            person,
            data={self.field.identifier: []},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors[self.field.identifier][0].code,
            "empty",
        )
        self.assertTrue(person.custom_values.filter(id=self.first.id).exists())


class ChoiceNormalizationTest(APITestCase):
    def value_choice_field(
        self,
        identifier: str,
        *,
        multiple: bool = False,
    ) -> tuple[CustomField, serializers.Field]:
        field = CustomFieldFactory(
            identifier=identifier,
            choice_field=True,
            multiple=multiple,
        )
        serializer_field = field.serializer_field
        serializer_field.set_unique_field("value")
        return field, serializer_field

    def test_single_value_lookup_accepts_pk_alias(self) -> None:
        field = CustomFieldFactory(identifier="pk_choice", choice_field=True)
        choice = CustomValueFactory(field=field)
        serializer = PrimaryKeyChoicePersonSerializer(
            data={"firstname": "Primary key", field.identifier: str(choice.pk)}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertSetEqual(
            set(person.custom_values.values_list("pk", flat=True)), {choice.pk}
        )

    def test_multiple_value_lookup_accepts_pk_alias(self) -> None:
        field = CustomFieldFactory(
            identifier="multiple_pk_choices", choice_field=True, multiple=True
        )
        first = CustomValueFactory(field=field)
        second = CustomValueFactory(field=field)
        serializer = PrimaryKeyChoicePersonSerializer(
            data={
                "firstname": "Primary keys",
                field.identifier: [str(first.pk), {"pk": second.pk}],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertSetEqual(
            set(person.custom_values.values_list("pk", flat=True)),
            {first.pk, second.pk},
        )

    def test_boolean_values_are_valid_for_json_choice_lookups(self) -> None:
        single_field = CustomFieldFactory(
            identifier="single_boolean_choice",
            choice_field=True,
            field_type=CustomField.FIELD_TYPES.BOOLEAN,
        )
        true_choice = CustomValueFactory(field=single_field, value=True)
        multiple_field = CustomFieldFactory(
            identifier="multiple_boolean_choices",
            choice_field=True,
            field_type=CustomField.FIELD_TYPES.BOOLEAN,
            multiple=True,
        )
        multiple_true = CustomValueFactory(field=multiple_field, value=True)
        multiple_false = CustomValueFactory(field=multiple_field, value=False)
        serializer = ValueChoicePersonSerializer(
            data={
                "firstname": "Boolean",
                single_field.identifier: True,
                multiple_field.identifier: [True, False],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertSetEqual(
            set(person.custom_values.values_list("id", flat=True)),
            {true_choice.id, multiple_true.id, multiple_false.id},
        )

    def test_json_choice_lookup_distinguishes_booleans_and_integers(self) -> None:
        field = CustomFieldFactory(
            identifier="typed_json_choices",
            choice_field=True,
            multiple=True,
        )
        choices = [
            CustomValueFactory(field=field, value=value)
            for value in (True, 1, False, 0)
        ]
        serializer = ValueChoicePersonSerializer(
            data={
                "firstname": "Typed JSON",
                field.identifier: [True, 1, False, 0],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertSetEqual(
            set(person.custom_values.values_list("id", flat=True)),
            {choice.id for choice in choices},
        )

    def test_single_json_choice_lookup_distinguishes_integers_and_floats(
        self,
    ) -> None:
        field = CustomFieldFactory(
            identifier="single_numeric_json_choice",
            choice_field=True,
        )
        integer_choice = CustomValueFactory(field=field, value=1)
        float_choice = CustomValueFactory(field=field, value=1.0)
        serializer_field = field.serializer_field
        serializer_field.set_unique_field("value")

        with self.assertNumQueries(1):
            validated_integer = serializer_field.run_validation(1)
        with self.assertNumQueries(1):
            validated_float = serializer_field.run_validation(1.0)

        self.assertEqual(validated_integer, integer_choice)
        self.assertEqual(validated_float, float_choice)

    def test_multiple_json_choice_lookup_distinguishes_integers_and_floats(
        self,
    ) -> None:
        field = CustomFieldFactory(
            identifier="multiple_numeric_json_choices",
            choice_field=True,
            multiple=True,
        )
        integer_choice = CustomValueFactory(field=field, value=1)
        float_choice = CustomValueFactory(field=field, value=1.0)
        serializer_field = field.serializer_field
        serializer_field.set_unique_field("value")

        with self.assertNumQueries(1):
            validated = serializer_field.run_validation([1.0, 1])

        self.assertIsInstance(validated, list)
        self.assertEqual(validated, [float_choice, integer_choice])

    def test_json_choice_lookup_matches_postgresql_normalized_negative_zero(
        self,
    ) -> None:
        field = CustomFieldFactory(
            identifier="negative_zero_json_choice",
            choice_field=True,
        )
        choice = CustomValueFactory(field=field, value=-0.0)
        serializer_field = field.serializer_field
        serializer_field.set_unique_field("value")

        choice.refresh_from_db()
        with self.assertNumQueries(1):
            validated = serializer_field.run_validation(-0.0)

        self.assertEqual(choice.value, 0.0)
        self.assertEqual(validated, choice)

    def test_json_choice_rejects_postgresql_incompatible_unicode_before_query(
        self,
    ) -> None:
        invalid_values = (
            "\x00",
            {"nested": "\x00"},
            {"\x00": "value"},
            "\ud800",
            "\udfff",
            {"nested": "\ud800"},
            {"\udfff": "value"},
        )

        for multiple in (False, True):
            _field, serializer_field = self.value_choice_field(
                f"invalid_unicode_{multiple}",
                multiple=multiple,
            )
            for value in invalid_values:
                data = [{"value": value}] if multiple else value
                with self.subTest(multiple=multiple, value=ascii(value)):
                    with (
                        self.assertNumQueries(0),
                        self.assertRaises(ValidationError) as error,
                    ):
                        serializer_field.run_validation(data)

                    self.assertEqual(error.exception.get_codes(), ["invalid"])

    def test_json_choice_accepts_astral_unicode_and_surrogate_pair_equally(
        self,
    ) -> None:
        field, serializer_field = self.value_choice_field("unicode_choice")
        choice = CustomValueFactory(field=field, value="😀")

        with self.assertNumQueries(1):
            astral = serializer_field.run_validation("😀")
        with self.assertNumQueries(1):
            surrogate_pair = serializer_field.run_validation("\ud83d\ude00")

        self.assertEqual(astral, choice)
        self.assertEqual(surrogate_pair, choice)

    def test_equivalent_unicode_choices_are_duplicates_before_query(self) -> None:
        field, serializer_field = self.value_choice_field(
            "duplicate_unicode_choices",
            multiple=True,
        )
        CustomValueFactory(field=field, value="😀")

        with self.assertNumQueries(0), self.assertRaises(ValidationError) as error:
            serializer_field.run_validation(["😀", "\ud83d\ude00"])

        self.assertEqual(error.exception.get_codes(), ["duplicate"])

    def test_json_choice_normalizes_mixed_object_keys_like_postgresql(self) -> None:
        field, serializer_field = self.value_choice_field("mixed_key_choice")
        choice = CustomValueFactory(field=field, value={"1": "last"})

        with self.assertNumQueries(1):
            validated = serializer_field.run_validation(
                {"value": {1: "first", "1": "last"}}
            )

        self.assertEqual(validated, choice)

    def test_json_choice_uses_last_key_after_json_key_coercion(self) -> None:
        field, serializer_field = self.value_choice_field("coerced_key_choice")
        choice = CustomValueFactory(field=field, value={"1": "last"})

        with self.assertNumQueries(1):
            validated = serializer_field.run_validation(
                {"value": {"1": "first", 1: "last"}}
            )

        self.assertEqual(validated, choice)

    def test_malformed_json_structures_are_rejected_before_query(self) -> None:
        field, serializer_field = self.value_choice_field("malformed_structure")
        cyclic: list[object] = []
        cyclic.append(cyclic)
        deeply_nested: object = None
        for _index in range(2_000):
            deeply_nested = [deeply_nested]

        invalid_values = (
            cyclic,
            deeply_nested,
            {("unsupported",): "key"},
            float("nan"),
            float("inf"),
            float("-inf"),
        )
        for value in invalid_values:
            with self.subTest(value=type(value).__name__):
                with (
                    self.assertNumQueries(0),
                    self.assertRaises(ValidationError) as error,
                ):
                    serializer_field.run_validation({"value": value})

                self.assertEqual(error.exception.get_codes(), ["invalid"])

        # Invalid JSON must not leave the surrounding test transaction unusable.
        self.assertEqual(field.choices.count(), 0)

    def test_single_json_numeric_lookup_preserves_specific_error_codes(self) -> None:
        missing_field = CustomFieldFactory(
            identifier="missing_numeric_json_choice",
            choice_field=True,
        )
        CustomValueFactory(field=missing_field, value=1.0)
        missing_serializer_field = missing_field.serializer_field
        missing_serializer_field.set_unique_field("value")

        with self.assertNumQueries(1), self.assertRaises(ValidationError) as missing:
            missing_serializer_field.run_validation(1)

        ambiguous_field = CustomFieldFactory(
            identifier="ambiguous_numeric_json_choice",
            choice_field=True,
        )
        CustomValueFactory(field=ambiguous_field, value=1)
        CustomValueFactory(field=ambiguous_field, value=1)
        ambiguous_serializer_field = ambiguous_field.serializer_field
        ambiguous_serializer_field.set_unique_field("value")

        with self.assertNumQueries(1), self.assertRaises(ValidationError) as ambiguous:
            ambiguous_serializer_field.run_validation(1)

        self.assertEqual(missing.exception.get_codes(), ["does_not_exist"])
        self.assertEqual(ambiguous.exception.get_codes(), ["multiple_matches"])

    def test_json_choice_lookup_still_rejects_exact_boolean_duplicates(self) -> None:
        field = CustomFieldFactory(
            identifier="duplicate_json_choices",
            choice_field=True,
            multiple=True,
        )
        CustomValueFactory(field=field, value=True)
        serializer = ValueChoicePersonSerializer(
            data={
                "firstname": "Duplicate JSON",
                field.identifier: [True, True],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors[field.identifier][0].code, "duplicate")

    def test_json_choice_lookup_rejects_non_json_numeric_values(self) -> None:
        field = CustomFieldFactory(
            identifier="invalid_json_number",
            choice_field=True,
        )
        serializer = ValueChoicePersonSerializer(
            data={"firstname": "Invalid JSON", field.identifier: float("nan")}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors[field.identifier][0].code, "invalid")

    def test_json_object_lookup_uses_canonical_key_order(self) -> None:
        field = CustomFieldFactory(
            identifier="json_object_choice",
            choice_field=True,
            multiple=True,
        )
        CustomValueFactory(field=field, value={"first": 1, "second": 2})
        serializer = ValueChoicePersonSerializer(
            data={
                "firstname": "JSON object",
                field.identifier: [
                    {"value": {"first": 1, "second": 2}},
                    {"value": {"second": 2, "first": 1}},
                ],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors[field.identifier][0].code, "duplicate")

    def test_boolean_does_not_alias_an_integer_primary_key(self) -> None:
        field = CustomFieldFactory(identifier="integer_id", choice_field=True)
        CustomValueFactory(field=field)
        serializer = TypeAwarePersonSerializer(
            data={"firstname": "Boolean ID", field.identifier: True}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors[field.identifier][0].code, "invalid")

    def test_single_value_lookup_rejects_ambiguous_configured_choices(self) -> None:
        field = CustomFieldFactory(identifier="ambiguous_single", choice_field=True)
        CustomValueFactory(field=field, value="duplicate")
        CustomValueFactory(field=field, value="duplicate")
        serializer = ValueChoicePersonSerializer(
            data={"firstname": "Ambiguous", field.identifier: "duplicate"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors[field.identifier][0].code,
            "multiple_matches",
        )

    def test_multiple_value_lookup_rejects_ambiguous_configured_choices(self) -> None:
        field = CustomFieldFactory(
            identifier="ambiguous_multiple",
            choice_field=True,
            multiple=True,
        )
        CustomValueFactory(field=field, value="duplicate")
        CustomValueFactory(field=field, value="duplicate")
        serializer = ValueChoicePersonSerializer(
            data={"firstname": "Ambiguous", field.identifier: ["duplicate"]}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors[field.identifier][0].code,
            "multiple_matches",
        )

    def test_uuid_strings_are_normalized_by_the_model_field(self) -> None:
        field = CustomFieldFactory(identifier="uuid_choice", choice_field=True)
        value = uuid4()
        custom_value_model = MagicMock()
        field_info = MagicMock(fields_and_pk={"id": models.UUIDField()})

        with (
            patch(
                "django_features.custom_fields.fields.get_custom_value_model",
                return_value=custom_value_model,
            ) as get_custom_value_model,
            patch(
                "django_features.custom_fields.fields.get_field_info",
                return_value=field_info,
            ) as get_field_info,
        ):
            serializer_field = field.serializer_field
            normalized = serializer_field._normalize_choice(str(value))
            with self.assertRaises(ValidationError):
                serializer_field._normalize_choice(True)

        self.assertEqual(normalized, value)
        get_custom_value_model.assert_called_once_with()
        get_field_info.assert_called_once_with(custom_value_model)
