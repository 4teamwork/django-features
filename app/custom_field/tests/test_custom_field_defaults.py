from typing import Any

from rest_framework import serializers
from rest_framework.fields import empty

from app.custom_field.models import CustomField
from app.custom_field.models import CustomValue
from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.models import Person
from app.tests import APITestCase
from app.tests.factories import PersonFactory
from django_features.serializers import BaseMappingSerializer


class ValueLookupBaseMappingPersonSerializer(BaseMappingSerializer):
    class Meta:
        model = Person
        fields = "__all__"

    @property
    def mapping(self) -> dict[str, Any]:
        return getattr(
            self,
            "_mapping",
            {
                "unique_choice_field": "value",
                "person": {
                    "firstname": "firstname",
                    "single_default": "single_default",
                    "multiple_default": "multiple_default",
                },
            },
        )

    @mapping.setter
    def mapping(self, value: dict[str, Any]) -> None:
        self._mapping = value


class CustomFieldDefaultTest(APITestCase):
    def _create(self) -> Person:
        serializer = TypeAwarePersonSerializer(
            data={"firstname": "Default", "lastname": "Values"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def _choice_defaults(
        self,
        *,
        editable: bool = True,
    ) -> tuple[CustomValue, CustomValue, CustomValue]:
        single = CustomFieldFactory(
            identifier="single_default",
            choice_field=True,
            editable=editable,
        )
        single_choice = CustomValueFactory(
            field=single,
            value="single-value",
        )
        single.default = single_choice.pk
        single.save(update_fields=["default"])

        multiple = CustomFieldFactory(
            identifier="multiple_default",
            choice_field=True,
            multiple=True,
            editable=editable,
        )
        first = CustomValueFactory(field=multiple, value="first-value")
        second = CustomValueFactory(field=multiple, value="second-value")
        multiple.default = [second.pk, first.pk]
        multiple.save(update_fields=["default"])
        return single_choice, first, second

    def _assert_choice_defaults(
        self,
        serializer: serializers.Serializer,
        single: CustomValue,
        first: CustomValue,
        second: CustomValue,
    ) -> Person:
        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(serializer.data["single_default"]["id"], single.pk)
        self.assertEqual(
            [choice["id"] for choice in serializer.data["multiple_default"]],
            [second.pk, first.pk],
        )

        person.refresh_with_custom_fields()
        self.assertEqual(person.single_default["id"], single.pk)
        self.assertSetEqual(
            {choice["id"] for choice in person.multiple_default},
            {first.pk, second.pk},
        )
        return person

    def test_all_falsy_scalar_and_list_defaults_are_applied(self) -> None:
        CustomFieldFactory(
            identifier="false_default",
            field_type=CustomField.FIELD_TYPES.BOOLEAN,
            default=False,
        )
        CustomFieldFactory(
            identifier="zero_default",
            field_type=CustomField.FIELD_TYPES.INTEGER,
            default=0,
        )
        CustomFieldFactory(identifier="blank_default", default="")
        CustomFieldFactory(
            identifier="empty_list_default",
            field_type=CustomField.FIELD_TYPES.INTEGER,
            multiple=True,
            default=[],
        )
        CustomFieldFactory(
            identifier="list_default",
            field_type=CustomField.FIELD_TYPES.INTEGER,
            multiple=True,
            default=[0, 1],
        )

        person = self._create()
        person.refresh_with_custom_fields()

        self.assertIs(person.false_default, False)
        self.assertEqual(person.zero_default, 0)
        self.assertEqual(person.blank_default, "")
        self.assertEqual(person.empty_list_default, [])
        self.assertEqual(person.list_default, [0, 1])

    def test_single_and_multiple_choice_defaults_are_applied(self) -> None:
        single, first, second = self._choice_defaults()
        serializer = TypeAwarePersonSerializer(data={"firstname": "Ordinary defaults"})

        self._assert_choice_defaults(serializer, single, first, second)

    def test_base_mapping_uses_the_same_pk_choice_defaults(self) -> None:
        single, first, second = self._choice_defaults()
        serializer = ValueLookupBaseMappingPersonSerializer(
            data={"firstname": "Mapping defaults"}
        )

        self._assert_choice_defaults(serializer, single, first, second)

    def test_noneditable_base_mapping_uses_the_same_pk_choice_defaults(self) -> None:
        single, first, second = self._choice_defaults(editable=False)
        serializer = ValueLookupBaseMappingPersonSerializer(
            data={"firstname": "Managed mapping defaults"}
        )

        self._assert_choice_defaults(serializer, single, first, second)

    def test_choice_default_resolution_is_batched_and_restores_value_lookup(
        self,
    ) -> None:
        single, first, second = self._choice_defaults()
        single_field = single.field.serializer_field
        single_field.set_unique_field("value")
        multiple_field = first.field.serializer_field
        multiple_field.set_unique_field("value")

        with self.assertNumQueries(1):
            validated_single = single_field.run_validation(empty)
        with self.assertNumQueries(1):
            validated_multiple = multiple_field.run_validation(empty)

        self.assertEqual(validated_single, single)
        self.assertEqual(validated_multiple, [second, first])
        self.assertEqual(single_field._unique_field, "value")
        self.assertEqual(multiple_field._unique_field, "value")

    def test_base_mapping_request_values_still_use_the_configured_lookup(self) -> None:
        single_field = CustomFieldFactory(
            identifier="single_default",
            choice_field=True,
        )
        default_single = CustomValueFactory(
            field=single_field,
            value="default-single",
        )
        requested_single = CustomValueFactory(
            field=single_field,
            value="requested-single",
        )
        single_field.default = default_single.pk
        single_field.save(update_fields=["default"])

        multiple_field = CustomFieldFactory(
            identifier="multiple_default",
            choice_field=True,
            multiple=True,
        )
        default_multiple = CustomValueFactory(
            field=multiple_field,
            value="default-multiple",
        )
        first_requested = CustomValueFactory(
            field=multiple_field,
            value="first-requested",
        )
        second_requested = CustomValueFactory(
            field=multiple_field,
            value="second-requested",
        )
        multiple_field.default = [default_multiple.pk]
        multiple_field.save(update_fields=["default"])

        serializer = ValueLookupBaseMappingPersonSerializer(
            data={
                "firstname": "Explicit mapping values",
                "single_default": requested_single.value,
                "multiple_default": [
                    second_requested.value,
                    first_requested.value,
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()
        self.assertSetEqual(
            set(person.custom_values.values_list("pk", flat=True)),
            {requested_single.pk, first_requested.pk, second_requested.pk},
        )

    def test_list_options_are_not_copied_to_the_child_field(self) -> None:
        custom_field = CustomFieldFactory(
            identifier="list_options",
            field_type=CustomField.FIELD_TYPES.INTEGER,
            multiple=True,
            required=False,
            allow_blank=False,
            allow_null=False,
        )

        serializer_field = custom_field.serializer_field

        self.assertIsInstance(serializer_field, serializers.ListField)
        self.assertFalse(serializer_field.required)
        self.assertFalse(serializer_field.allow_empty)
        self.assertFalse(serializer_field.allow_null)
        self.assertTrue(serializer_field.child.required)
        self.assertFalse(serializer_field.child.allow_null)

    def test_invalid_configured_default_is_validated(self) -> None:
        CustomFieldFactory(
            identifier="invalid_default",
            field_type=CustomField.FIELD_TYPES.INTEGER,
            default="not-an-integer",
        )

        serializer = TypeAwarePersonSerializer(data={"firstname": "Invalid"})
        self.assertFalse(serializer.is_valid())

    def test_choice_defaults_do_not_fall_back_to_value_lookup(self) -> None:
        single = CustomFieldFactory(identifier="single_default", choice_field=True)
        single_choice = CustomValueFactory(field=single, value="legacy-single")
        single.default = single_choice.value
        single.save(update_fields=["default"])
        multiple = CustomFieldFactory(
            identifier="multiple_default",
            choice_field=True,
            multiple=True,
        )
        first = CustomValueFactory(field=multiple, value="legacy-first")
        second = CustomValueFactory(field=multiple, value="legacy-second")
        multiple.default = [first.value, second.value]
        multiple.save(update_fields=["default"])

        for serializer_class in (
            TypeAwarePersonSerializer,
            ValueLookupBaseMappingPersonSerializer,
        ):
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data={"firstname": "Legacy defaults"})

                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    serializer.errors[single.identifier][0].code,
                    "invalid",
                )
                self.assertEqual(
                    serializer.errors[multiple.identifier][0].code,
                    "invalid",
                )

    def test_invalid_choice_pk_defaults_preserve_specific_error_codes(self) -> None:
        single = CustomFieldFactory(
            identifier="single_default",
            choice_field=True,
            default=999_999,
        )
        multiple = CustomFieldFactory(
            identifier="multiple_default",
            choice_field=True,
            multiple=True,
        )
        choice = CustomValueFactory(field=multiple)
        multiple.default = [choice.pk, str(choice.pk)]
        multiple.save(update_fields=["default"])

        for serializer_class in (
            TypeAwarePersonSerializer,
            ValueLookupBaseMappingPersonSerializer,
        ):
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data={"firstname": "Invalid PKs"})

                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    serializer.errors[single.identifier][0].code,
                    "does_not_exist",
                )
                self.assertEqual(
                    serializer.errors[multiple.identifier][0].code,
                    "duplicate",
                )

    def test_invalid_configured_default_is_not_applied_on_update(self) -> None:
        custom_field = CustomFieldFactory(
            identifier="invalid_update_default",
            field_type=CustomField.FIELD_TYPES.INTEGER,
            default="not-an-integer",
        )
        person = PersonFactory(firstname="Before")
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After", "lastname": person.lastname},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertFalse(person.custom_values.filter(field=custom_field).exists())

    def test_required_field_takes_precedence_over_configured_default(self) -> None:
        custom_field = CustomFieldFactory(
            identifier="required_with_default",
            field_type=CustomField.FIELD_TYPES.INTEGER,
            required=True,
            default=1,
        )
        serializer = TypeAwarePersonSerializer(data={"firstname": "Required"})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors[custom_field.identifier][0].code, "required")

    def test_empty_choice_default_respects_allow_blank(self) -> None:
        CustomFieldFactory(identifier="single_default", choice_field=True)
        custom_field = CustomFieldFactory(
            identifier="multiple_default",
            choice_field=True,
            multiple=True,
            allow_blank=False,
            default=[],
        )

        for serializer_class in (
            TypeAwarePersonSerializer,
            ValueLookupBaseMappingPersonSerializer,
        ):
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data={"firstname": "Invalid"})

                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    serializer.errors[custom_field.identifier][0].code,
                    "empty",
                )
