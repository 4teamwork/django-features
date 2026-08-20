from typing import Any
from typing import ClassVar
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.models import Address
from app.models import Person
from app.models import PersonType
from app.tests import APITestCase
from app.tests.factories import PersonFactory
from app.tests.factories import PersonTypeFactory
from django_features.custom_fields.serializers import CustomFieldBaseModelSerializer
from django_features.custom_fields.serializers import CustomFieldListSerializer


class CountingPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    conversion_calls: ClassVar[int] = 0

    def to_internal_value(self, data: Any) -> Any:
        type(self).conversion_calls += 1
        return super().to_internal_value(data)


class CountingTypePersonSerializer(TypeAwarePersonSerializer):
    person_type = CountingPrimaryKeyRelatedField(
        allow_null=True,
        queryset=PersonType.objects.all(),
        required=False,
    )


class UntypedAddressSerializer(CustomFieldBaseModelSerializer):
    class Meta:
        model = Address
        fields = ["city"]


class CopyingCustomFieldListSerializer(CustomFieldListSerializer):
    def validate(self, attrs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list(attrs)


class ReorderingCustomFieldListSerializer(CustomFieldListSerializer):
    def validate(self, attrs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list(reversed(attrs))


class ReplacingCustomFieldListSerializer(CustomFieldListSerializer):
    def validate(self, attrs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [dict(item) for item in attrs]


class DroppingCustomFieldListSerializer(CustomFieldListSerializer):
    def validate(self, attrs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return attrs[:-1]


class ExpandingCustomFieldListSerializer(CustomFieldListSerializer):
    def validate(self, attrs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [*attrs, dict(attrs[-1])]


class RetypingCustomFieldListSerializer(CustomFieldListSerializer):
    def validate(self, attrs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        attrs[0]["person_type"] = attrs[1]["person_type"]
        return attrs


class RemappingCustomFieldListSerializer(ReorderingCustomFieldListSerializer):
    def get_paired_item_serializers(
        self,
        validated_data: list[Any],
    ) -> list[CustomFieldBaseModelSerializer]:
        if len(validated_data) != len(self._validated_item_serializers):
            raise AssertionError("The reverse pairing requires unchanged cardinality.")
        return list(reversed(self._validated_item_serializers))


class IncompletePairingCustomFieldListSerializer(CustomFieldListSerializer):
    def get_paired_item_serializers(
        self,
        validated_data: list[Any],
    ) -> list[CustomFieldBaseModelSerializer]:
        return []


class CopyingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = CopyingCustomFieldListSerializer


class ReorderingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = ReorderingCustomFieldListSerializer


class ReplacingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = ReplacingCustomFieldListSerializer


class DroppingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = DroppingCustomFieldListSerializer


class ExpandingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = ExpandingCustomFieldListSerializer


class RetypingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = RetypingCustomFieldListSerializer


class RemappingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = RemappingCustomFieldListSerializer


class IncompletePairingListPersonSerializer(TypeAwarePersonSerializer):
    class Meta(TypeAwarePersonSerializer.Meta):
        list_serializer_class = IncompletePairingCustomFieldListSerializer


class CustomFieldSerializerStructureTest(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.type_content_type = ContentType.objects.get_for_model(PersonType)
        self.first_type = PersonTypeFactory(title="First")
        self.second_type = PersonTypeFactory(title="Second")
        self.first_field = CustomFieldFactory(
            identifier="first_value",
            type_content_type=self.type_content_type,
            type_id=self.first_type.pk,
        )
        self.second_field = CustomFieldFactory(
            identifier="second_value",
            type_content_type=self.type_content_type,
            type_id=self.second_type.pk,
        )

    def type_aware_data(self) -> list[dict[str, Any]]:
        return [
            {
                "firstname": "First person",
                "person_type": self.first_type.pk,
                "first_value": "first",
            },
            {
                "firstname": "Second person",
                "person_type": self.second_type.pk,
                "second_value": "second",
            },
        ]

    def test_type_resolution_before_fields_is_cached_without_recursion(self) -> None:
        CountingPrimaryKeyRelatedField.conversion_calls = 0
        serializer = CountingTypePersonSerializer(
            data={
                "firstname": "First person",
                "person_type": self.first_type.pk,
                "first_value": "first",
            }
        )

        self.assertEqual(serializer.get_custom_field_type_id(), self.first_type.pk)
        self.assertEqual(serializer.get_custom_field_type_id(), self.first_type.pk)
        self.assertEqual(CountingPrimaryKeyRelatedField.conversion_calls, 1)

        self.assertIn("first_value", serializer.fields)
        self.assertNotIn("second_value", serializer.fields)
        self.assertEqual(CountingPrimaryKeyRelatedField.conversion_calls, 1)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(CountingPrimaryKeyRelatedField.conversion_calls, 2)

    def test_many_items_resolve_fields_and_representation_independently(self) -> None:
        serializer = TypeAwarePersonSerializer(data=self.type_aware_data(), many=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        item_serializers = serializer._validated_item_serializers
        self.assertIn("first_value", item_serializers[0].fields)
        self.assertNotIn("second_value", item_serializers[0].fields)
        self.assertIn("second_value", item_serializers[1].fields)
        self.assertNotIn("first_value", item_serializers[1].fields)

        first_person, second_person = serializer.save()

        self.assertTrue(
            first_person.custom_values.filter(field=self.first_field).exists()
        )
        self.assertFalse(
            first_person.custom_values.filter(field=self.second_field).exists()
        )
        self.assertTrue(
            second_person.custom_values.filter(field=self.second_field).exists()
        )
        self.assertFalse(
            second_person.custom_values.filter(field=self.first_field).exists()
        )
        self.assertEqual(serializer.data[0]["first_value"], "first")
        self.assertNotIn("second_value", serializer.data[0])
        self.assertEqual(serializer.data[1]["second_value"], "second")
        self.assertNotIn("first_value", serializer.data[1])

    def test_validated_data_representation_uses_paired_item_serializers(self) -> None:
        serializer = TypeAwarePersonSerializer(data=self.type_aware_data(), many=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.data[0]["first_value"], "first")
        self.assertNotIn("second_value", serializer.data[0])
        self.assertEqual(serializer.data[1]["second_value"], "second")
        self.assertNotIn("first_value", serializer.data[1])

    def test_default_pairing_accepts_a_new_list_with_preserved_positions(self) -> None:
        serializer = CopyingListPersonSerializer(
            data=self.type_aware_data(),
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        first_person, second_person = serializer.save()

        self.assertEqual(first_person.person_type, self.first_type)
        self.assertEqual(second_person.person_type, self.second_type)
        self.assertTrue(
            first_person.custom_values.filter(field=self.first_field).exists()
        )
        self.assertTrue(
            second_person.custom_values.filter(field=self.second_field).exists()
        )

    def test_default_pairing_rejects_reordered_or_replaced_items(self) -> None:
        for serializer_class in (
            ReorderingListPersonSerializer,
            ReplacingListPersonSerializer,
        ):
            with self.subTest(serializer_class=serializer_class.__name__):
                serializer = serializer_class(data=self.type_aware_data(), many=True)

                with self.assertRaisesRegex(
                    AssertionError,
                    "replaced or reordered custom-field serializer items",
                ):
                    serializer.is_valid()

    def test_default_pairing_rejects_item_count_changes(self) -> None:
        for serializer_class in (
            DroppingListPersonSerializer,
            ExpandingListPersonSerializer,
        ):
            with self.subTest(serializer_class=serializer_class.__name__):
                serializer = serializer_class(data=self.type_aware_data(), many=True)

                with self.assertRaisesRegex(
                    AssertionError,
                    "changed the number of custom-field serializer items",
                ):
                    serializer.is_valid()

    def test_default_pairing_rejects_an_in_place_type_change(self) -> None:
        serializer = RetypingListPersonSerializer(
            data=self.type_aware_data(),
            many=True,
        )

        with self.assertRaisesRegex(
            AssertionError,
            "changed the custom-field type selected for item 0",
        ):
            serializer.is_valid()

    def test_save_rejects_reordering_after_validation(self) -> None:
        serializer = TypeAwarePersonSerializer(data=self.type_aware_data(), many=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        serializer.validated_data.reverse()

        with self.assertRaisesRegex(
            AssertionError,
            "replaced or reordered after custom-field serializer pairing",
        ):
            serializer.save()
        self.assertEqual(Person._base_manager.count(), 0)

    def test_save_kwargs_cannot_change_the_selected_type(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data=[self.type_aware_data()[0]],
            many=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaisesRegex(
            AssertionError,
            "changed the custom-field type selected for item 0",
        ):
            serializer.save(person_type=self.second_type)
        self.assertEqual(Person._base_manager.count(), 0)

    def test_single_save_kwargs_cannot_change_the_selected_type(self) -> None:
        serializer = TypeAwarePersonSerializer(data=self.type_aware_data()[0])
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(serializers.ValidationError):
            serializer.save(person_type=self.second_type)
        self.assertEqual(Person._base_manager.count(), 0)

    def test_single_update_cannot_bypass_type_selection_with_attname(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        serializer = TypeAwarePersonSerializer(
            person,
            data={"first_value": "first"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(serializers.ValidationError):
            serializer.save(person_type_id=self.second_type.pk)

        person.refresh_from_db()
        self.assertEqual(person.person_type, self.first_type)
        self.assertFalse(person.custom_values.exists())

    def test_single_update_allows_matching_type_attname(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        serializer = TypeAwarePersonSerializer(
            person,
            data={"first_value": "first"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        person = serializer.save(person_type_id=self.first_type.pk)

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(person.custom_values.filter(field=self.first_field).exists())

    def test_pairing_hook_can_support_an_intentional_reorder(self) -> None:
        serializer = RemappingListPersonSerializer(
            data=self.type_aware_data(),
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        first_created, second_created = serializer.save()

        self.assertEqual(first_created.firstname, "Second person")
        self.assertEqual(first_created.person_type, self.second_type)
        self.assertTrue(
            first_created.custom_values.filter(field=self.second_field).exists()
        )
        self.assertEqual(second_created.firstname, "First person")
        self.assertEqual(second_created.person_type, self.first_type)
        self.assertTrue(
            second_created.custom_values.filter(field=self.first_field).exists()
        )
        self.assertEqual(serializer.data[0]["second_value"], "second")
        self.assertNotIn("first_value", serializer.data[0])
        self.assertEqual(serializer.data[1]["first_value"], "first")
        self.assertNotIn("second_value", serializer.data[1])

    def test_pairing_hook_applies_to_validated_data_representation(self) -> None:
        serializer = RemappingListPersonSerializer(
            data=self.type_aware_data(),
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.data[0]["firstname"], "Second person")
        self.assertEqual(serializer.data[0]["second_value"], "second")
        self.assertNotIn("first_value", serializer.data[0])
        self.assertEqual(serializer.data[1]["firstname"], "First person")
        self.assertEqual(serializer.data[1]["first_value"], "first")
        self.assertNotIn("second_value", serializer.data[1])

    def test_pairing_hook_must_return_one_serializer_per_item(self) -> None:
        serializer = IncompletePairingListPersonSerializer(
            data=self.type_aware_data(),
            many=True,
        )

        with self.assertRaisesRegex(
            AssertionError,
            "must return one custom-field serializer for every validated list item",
        ):
            serializer.is_valid()

    def test_untyped_custom_field_serializer_still_supports_many_create(self) -> None:
        address_field = CustomFieldFactory(
            content_type=ContentType.objects.get_for_model(Address),
            identifier="delivery_note",
        )
        serializer = UntypedAddressSerializer(
            data=[
                {"city": "Bern", "delivery_note": "front desk"},
                {"city": "Zürich", "delivery_note": "side door"},
            ],
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        first_address, second_address = serializer.save()

        self.assertIsNone(serializer.child.get_custom_field_type_id())
        self.assertTrue(
            first_address.custom_values.filter(field=address_field).exists()
        )
        self.assertTrue(
            second_address.custom_values.filter(field=address_field).exists()
        )
        self.assertEqual(serializer.data[0]["delivery_note"], "front desk")
        self.assertEqual(serializer.data[1]["delivery_note"], "side door")

    def test_unknown_model_type_attribute_has_a_clear_configuration_error(self) -> None:
        with patch.object(Person, "_custom_field_type_attr", "missing_type"):
            serializer = TypeAwarePersonSerializer()

            with self.assertRaisesRegex(
                ImproperlyConfigured,
                "Person._custom_field_type_attr refers to unknown field "
                "'missing_type'",
            ):
                serializer.fields

    def test_non_relational_model_type_attribute_has_a_clear_error(self) -> None:
        with patch.object(Person, "_custom_field_type_attr", "firstname"):
            serializer = TypeAwarePersonSerializer()

            with self.assertRaisesRegex(
                ImproperlyConfigured,
                "Person._custom_field_type_attr must refer to a related model "
                "field; 'firstname' is not relational",
            ):
                serializer.fields

    def test_unknown_custom_field_type_has_an_identifier_scoped_error(self) -> None:
        CustomFieldFactory(
            identifier="invalid_value",
            field_type="not-a-field-type",
        )
        serializer = TypeAwarePersonSerializer()

        with self.assertRaises(ImproperlyConfigured) as raised:
            serializer.fields

        self.assertIn("'invalid_value'", str(raised.exception))
        self.assertIn("Unknown field type: not-a-field-type", str(raised.exception))
        self.assertIsInstance(raised.exception.__cause__, ValueError)

    def test_invalid_choice_lookup_has_an_identifier_scoped_error(self) -> None:
        CustomFieldFactory(
            identifier="invalid_choice_lookup",
            choice_field=True,
        )

        class InvalidChoiceLookupSerializer(TypeAwarePersonSerializer):
            _unique_choice_field = "missing_lookup"

        serializer = InvalidChoiceLookupSerializer()

        with self.assertRaises(ImproperlyConfigured) as raised:
            serializer.fields

        self.assertIn("'invalid_choice_lookup'", str(raised.exception))
        self.assertIn("invalid field missing_lookup", str(raised.exception))
        self.assertIsInstance(raised.exception.__cause__, ValueError)
