from rest_framework import serializers

from app.custom_field.models import CustomField
from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.models import Person
from app.tests import APITestCase
from app.tests.factories import PersonFactory


class CustomFieldDefaultTest(APITestCase):
    def _create(self) -> Person:
        serializer = TypeAwarePersonSerializer(
            data={"firstname": "Default", "lastname": "Values"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

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
        single = CustomFieldFactory(identifier="single_default", choice_field=True)
        single_choice = CustomValueFactory(field=single)
        single.default = single_choice.id
        single.save()
        multiple = CustomFieldFactory(
            identifier="multiple_default", choice_field=True, multiple=True
        )
        first = CustomValueFactory(field=multiple, value="first")
        second = CustomValueFactory(field=multiple, value="second")
        multiple.default = [first.id, second.id]
        multiple.save()

        person = self._create()
        person.refresh_with_custom_fields()

        self.assertEqual(person.single_default["id"], single_choice.id)
        self.assertEqual(
            {choice["id"] for choice in person.multiple_default},
            {first.id, second.id},
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
        custom_field = CustomFieldFactory(
            identifier="invalid_empty_choice_default",
            choice_field=True,
            multiple=True,
            allow_blank=False,
            default=[],
        )

        serializer = TypeAwarePersonSerializer(data={"firstname": "Invalid"})

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors[custom_field.identifier][0].code,
            "empty",
        )
