from typing import Any
from typing import ClassVar
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers
from rest_framework.fields import empty

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
        self.assertEqual(CountingPrimaryKeyRelatedField.conversion_calls, 1)

    def test_type_override_can_inspect_fields_during_outer_field_build(self) -> None:
        calls: list[set[str]] = []

        class InspectingTypePersonSerializer(TypeAwarePersonSerializer):
            def get_custom_field_type_id(self) -> int | None:
                calls.append(set(self.fields))
                return super().get_custom_field_type_id()

        serializer = InspectingTypePersonSerializer(
            data={
                "firstname": "Inspect fields",
                "person_type": self.first_type.pk,
                "first_value": "first",
            }
        )

        self.assertIn("first_value", serializer.fields)
        self.assertNotIn("second_value", serializer.fields)
        self.assertEqual(
            calls,
            [{"email", "firstname", "lastname", "person_type"}],
        )
        self.assertIs(serializer.fields["firstname"].parent, serializer)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_type_override_field_inspection_does_not_cache_default_type(self) -> None:
        calls: list[set[str]] = []

        class ContextTypePersonSerializer(TypeAwarePersonSerializer):
            def get_custom_field_type_id(self) -> int:
                calls.append(set(self.fields))
                return self.context["selected_type"].pk

        serializer = ContextTypePersonSerializer(
            data={
                "firstname": "Override fields",
                "person_type": self.first_type.pk,
            },
            context={"selected_type": self.second_type},
        )

        self.assertEqual(serializer.get_custom_field_type_id(), self.second_type.pk)
        self.assertNotIn("fields", serializer.__dict__)
        self.assertIn("second_value", serializer.fields)
        self.assertNotIn("first_value", serializer.fields)
        self.assertEqual(
            calls,
            [{"email", "firstname", "lastname", "person_type"}],
        )

    def test_nested_single_input_rebuilds_preinspected_fields_for_its_type(
        self,
    ) -> None:
        class PersonContainerSerializer(serializers.Serializer):
            person = TypeAwarePersonSerializer()

            def create(self, validated_data: dict[str, Any]) -> dict[str, Person]:
                child = self.fields["person"]
                return {"person": child.create(validated_data["person"])}

        serializer = PersonContainerSerializer(
            data={
                "person": {
                    "firstname": "Nested",
                    "person_type": self.first_type.pk,
                    "first_value": "nested value",
                }
            }
        )
        child = serializer.fields["person"]
        self.assertNotIn("first_value", child.fields)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn("first_value", child.fields)
        self.assertNotIn("second_value", child.fields)
        person = serializer.save()["person"]

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(
            person.custom_values.filter(
                field=self.first_field,
                value="nested value",
            ).exists()
        )
        self.assertEqual(serializer.data["person"]["first_value"], "nested value")

    def test_nested_field_inspection_defers_override_until_input_is_known(self) -> None:
        calls: list[set[str]] = []

        class InspectingTypePersonSerializer(TypeAwarePersonSerializer):
            def get_custom_field_type_id(self) -> int | None:
                calls.append(set(self.fields))
                return super().get_custom_field_type_id()

        class PersonContainerSerializer(serializers.Serializer):
            person = InspectingTypePersonSerializer()

        serializer = PersonContainerSerializer(
            data={
                "person": {
                    "firstname": "Nested override",
                    "person_type": self.first_type.pk,
                    "first_value": "nested value",
                }
            }
        )
        child = serializer.fields["person"]
        self.assertNotIn("first_value", child.fields)
        self.assertEqual(calls, [])

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn("first_value", child.fields)
        self.assertEqual(
            calls,
            [{"email", "firstname", "lastname", "person_type"}],
        )

    def test_direct_validation_recomputes_an_override_for_each_input(self) -> None:
        calls: list[int | None] = []

        class InspectingTypePersonSerializer(TypeAwarePersonSerializer):
            def get_custom_field_type_id(self) -> int | None:
                selected = super().get_custom_field_type_id()
                calls.append(selected)
                return selected

        serializer = InspectingTypePersonSerializer()

        first = serializer.run_validation(
            {
                "firstname": "First direct input",
                "person_type": self.first_type.pk,
                "first_value": "first",
            }
        )
        second = serializer.run_validation(
            {
                "firstname": "Second direct input",
                "person_type": self.second_type.pk,
                "second_value": "second",
            }
        )

        self.assertEqual(first["first_value"], "first")
        self.assertEqual(second["second_value"], "second")
        self.assertEqual(calls, [self.first_type.pk, self.second_type.pk])

    def test_nested_single_model_representation_uses_the_item_type(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        person.custom_values.create(field=self.first_field, value="stored")
        person = Person.objects.get(pk=person.pk)

        class PersonContainerSerializer(serializers.Serializer):
            person = TypeAwarePersonSerializer()

        data = PersonContainerSerializer({"person": person}).data

        self.assertEqual(data["person"]["first_value"], "stored")
        self.assertNotIn("second_value", data["person"])

    def test_nested_item_scope_runs_representation_override_once(self) -> None:
        calls: list[Person] = []

        class FormattingPersonSerializer(TypeAwarePersonSerializer):
            def to_representation(self, instance: Person) -> dict[str, Any]:
                calls.append(instance)
                data = super().to_representation(instance)
                data["formatted"] = True
                return data

        class PersonContainerSerializer(serializers.Serializer):
            person = FormattingPersonSerializer()

        person = PersonFactory(person_type=self.first_type)
        person.custom_values.create(field=self.first_field, value="stored")
        person = Person.objects.get(pk=person.pk)

        data = PersonContainerSerializer({"person": person}).data

        self.assertEqual(calls, [person])
        self.assertTrue(data["person"]["formatted"])
        self.assertEqual(data["person"]["first_value"], "stored")

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

    def test_nullable_many_input_short_circuits_without_pairing(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data=None,
            many=True,
            allow_null=True,
        )
        # Resolve the child fields first to cover the cached type-selection path.
        self.assertIn("firstname", serializer.child.fields)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data)
        self.assertEqual(serializer._paired_item_serializers, [])

    def test_nested_nullable_many_input_preserves_drf_null_semantics(self) -> None:
        class PeopleSerializer(serializers.Serializer):
            people = TypeAwarePersonSerializer(many=True, allow_null=True)

        serializer = PeopleSerializer(data={"people": None})
        self.assertIn("firstname", serializer.fields["people"].child.fields)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["people"])

    def test_many_callable_default_bypasses_item_and_list_validation(self) -> None:
        default_value = [
            {
                "firstname": "Already internal",
                "person_type": self.first_type,
                "first_value": "default",
            },
            {
                "firstname": "Second internal",
                "person_type": self.first_type,
                "first_value": "second default",
            },
            {
                "firstname": "Other type internal",
                "person_type": self.second_type,
                "second_value": "other default",
            },
        ]
        default_calls: list[str] = []
        validator_calls: list[Any] = []

        def get_default(serializer_field: serializers.Field) -> list[dict[str, Any]]:
            default_calls.append(serializer_field.field_name)
            return default_value

        setattr(get_default, "requires_context", True)

        def validate_list(value: Any) -> None:
            validator_calls.append(value)

        class PeopleSerializer(serializers.Serializer):
            people = TypeAwarePersonSerializer(
                many=True,
                default=get_default,
                validators=[validate_list],
            )

        serializer = PeopleSerializer(data={})
        list_serializer = serializer.fields["people"]
        self.assertIn("firstname", list_serializer.child.fields)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["people"], default_value)
        self.assertEqual(default_calls, ["people"])
        self.assertEqual(validator_calls, [])
        self.assertEqual(list_serializer._paired_item_serializers, [])
        # One definition query per distinct type; the repeated first type reuses
        # the list serializer's shared cache.
        with self.assertNumQueries(2):
            representation = serializer.data["people"]
        self.assertEqual(
            [item["first_value"] for item in representation[:2]],
            ["default", "second default"],
        )
        self.assertEqual(representation[2]["second_value"], "other default")
        self.assertFalse(any("second_value" in item for item in representation[:2]))
        self.assertNotIn("first_value", representation[2])

    def test_many_empty_default_is_not_treated_as_validated_input(self) -> None:
        class PeopleSerializer(serializers.Serializer):
            people = TypeAwarePersonSerializer(many=True, default=[])

        serializer = PeopleSerializer(data={})
        list_serializer = serializer.fields["people"]

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["people"], [])
        self.assertEqual(list_serializer._paired_item_serializers, [])
        self.assertEqual(list_serializer._paired_item_values, ())

    def test_many_validation_resets_pairing_after_a_default_short_circuit(
        self,
    ) -> None:
        default_value = [{"firstname": "Default"}]
        serializer = TypeAwarePersonSerializer(
            many=True,
            required=False,
            default=lambda: default_value,
        )

        validated = serializer.run_validation(self.type_aware_data())
        self.assertEqual(len(serializer._paired_item_serializers), 2)
        self.assertIs(serializer._validated_list_data, validated)

        short_circuited = serializer.run_validation(empty)

        self.assertIs(short_circuited, default_value)
        self.assertEqual(serializer._validated_item_serializers, [])
        self.assertEqual(serializer._paired_item_serializers, [])
        self.assertIsNot(serializer._validated_list_data, short_circuited)

    def test_single_nullable_input_short_circuits_type_validation(self) -> None:
        serializer = TypeAwarePersonSerializer(data=None, allow_null=True)
        self.assertIn("firstname", serializer.fields)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data)

    def test_single_default_bypasses_type_selection_validation(self) -> None:
        default_value = {
            "firstname": "Already internal",
            "person_type": self.first_type,
            "first_value": "default",
        }

        class PersonContainerSerializer(serializers.Serializer):
            person = TypeAwarePersonSerializer(default=default_value)

        serializer = PersonContainerSerializer(data={})
        child = serializer.fields["person"]
        self.assertIn("firstname", child.fields)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["person"], default_value)
        self.assertEqual(serializer.data["person"]["first_value"], "default")
        self.assertNotIn("second_value", serializer.data["person"])

    def test_converted_non_mapping_value_has_a_configuration_error(self) -> None:
        class NonMappingPersonSerializer(TypeAwarePersonSerializer):
            def to_internal_value(self, data: Any) -> list[Any]:
                return []

        serializer = NonMappingPersonSerializer(data={"firstname": "Invalid"})

        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "must return a mapping from to_internal_value",
        ):
            serializer.is_valid()

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
