from typing import Any

from app import models
from app.tests import APITestCase
from app.tests.factories import PersonFactory
from django_features.serializers import ListDataMappingSerializer
from django_features.serializers import MappingSerializer
from django_features.system_message.factories import SystemMessageFactory
from django_features.system_message.models import SystemMessage


class TestMappingSerializer(MappingSerializer):
    class Meta:
        model = models.Person
        fields = "__all__"

    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return {
            "person": {
                "external_base_field": "base_field",
                "external_single_field_1": "dict_field.nested_field_1",
                "external_single_field_2": "dict_field.nested_field_2",
                "external_dict_field.nested_field": "single_field",
                "external_object_field.nested_external_field_1": "object_field.nested_field_1",
                "external_object_field.nested_external_field_2": "object_field.nested_field_2",
                "external_object_field_with_object.external_object_field_1.external_field_1": "object_field_with_object.object_field_1.field_1",  # noqa: E501
                "external_object_field_with_object.external_object_field_1.external_field_2": "object_field_with_object.object_field_1.field_2",  # noqa: E501
                "external_object_field_with_object.external_object_field_2.external_field_1": "object_field_with_object.object_field_2.field_1",  # noqa: E501
                "external_object_field_with_object.external_object_field_2.external_field_2": "object_field_with_object.object_field_2.field_2",  # noqa: E501
            }
        }


class NullableFieldMappingSerializer(MappingSerializer):
    class Meta:
        model = models.Person
        fields = "__all__"

    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return {"person": {"external_nullable": "lastname"}}


class NonNullableFieldMappingSerializer(MappingSerializer):
    class Meta:
        model = models.Person
        fields = "__all__"

    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return {"person": {"external_non_nullable": "firstname"}}


class NestedFieldMappingSerializer(MappingSerializer):
    class Meta:
        model = models.Person
        fields = "__all__"

    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return {"person": {"external.nested_nullable": "lastname"}}


class DefaultFieldMappingSerializer(NullableFieldMappingSerializer):
    def default_lastname(self) -> str:
        self.default_calls = getattr(self, "default_calls", 0) + 1
        return "Default lastname"


class FormattingFieldMappingSerializer(NullableFieldMappingSerializer):
    def format_lastname(self, value: Any) -> Any:
        self.formatted_values = getattr(self, "formatted_values", [])
        self.formatted_values.append(value)
        return value


class DefaultAndFormattingFieldMappingSerializer(NullableFieldMappingSerializer):
    def default_lastname(self) -> str:
        return "Default lastname"

    def format_lastname(self, value: Any) -> str:
        return f"Formatted {value}"


class ContextAwareMappingSerializer(NullableFieldMappingSerializer):
    def default_lastname(self) -> str:
        return self.unmapped_data["fallback_lastname"]

    def format_lastname(self, value: Any) -> str:
        return f"{self.unmapped_data['title']} {value}"


class OverridingListSerializer(ListDataMappingSerializer):
    def map_list_data(self, initial_data: Any) -> Any:
        return [{"lastname": "Overridden lastname"} for _ in initial_data]


class CustomListMappingSerializer(NullableFieldMappingSerializer):
    class Meta(NullableFieldMappingSerializer.Meta):
        list_serializer_class = OverridingListSerializer


class DefaultedModelFieldMappingSerializer(MappingSerializer):
    class Meta:
        model = SystemMessage
        fields = "__all__"

    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return {"systemmessage": {"external_order": "order"}}


class MultipleNestedRelationsMappingSerializer(MappingSerializer):
    class Meta:
        model = models.Person
        fields = "__all__"

    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return {
            "person": {
                "external_firstname": "firstname",
                "external_municipality": "place_of_residence.title",
                "external_person_type": "person_type.title",
            }
        }


class MappingSerializerTestCase(APITestCase):
    def test_mapping_serializer_map_initial_data(self) -> None:
        data = {
            "external_base_field": "base_value",
            "external_single_field_1": "nested_value_1",
            "external_single_field_2": "nested_value_2",
            "external_dict_field": {"nested_field": "single_value"},
            "external_object_field": {
                "nested_external_field_1": "nested_value_1",
                "nested_external_field_2": "nested_value_2",
            },
            "external_object_field_with_object": {
                "external_object_field_1": {
                    "external_field_1": "value_1",
                    "external_field_2": "value_2",
                },
                "external_object_field_2": {
                    "external_field_1": "value_1",
                    "external_field_2": "value_2",
                },
            },
        }

        expected_data = {
            "base_field": "base_value",
            "dict_field": {
                "nested_field_1": "nested_value_1",
                "nested_field_2": "nested_value_2",
            },
            "single_field": "single_value",
            "object_field": {
                "nested_field_1": "nested_value_1",
                "nested_field_2": "nested_value_2",
            },
            "object_field_with_object": {
                "object_field_1": {"field_1": "value_1", "field_2": "value_2"},
                "object_field_2": {"field_1": "value_1", "field_2": "value_2"},
            },
        }

        mapped_data = TestMappingSerializer().map_data(data)
        self.assertEqual(mapped_data, expected_data)

    def test_missing_nullable_field_is_omitted_from_mapped_data(self) -> None:
        serializer = NullableFieldMappingSerializer(data={})

        self.assertEqual(serializer.initial_data, {})

    def test_explicit_none_remains_in_mapped_data(self) -> None:
        serializer = NullableFieldMappingSerializer(data={"external_nullable": None})

        self.assertEqual(serializer.initial_data, {"lastname": None})

    def test_allow_null_accepts_explicit_none(self) -> None:
        serializer = NullableFieldMappingSerializer(data={"external_nullable": None})

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data, {"lastname": None})

    def test_disallow_null_rejects_explicit_none(self) -> None:
        serializer = NonNullableFieldMappingSerializer(
            data={"external_non_nullable": None}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["firstname"][0].code, "null")

    def test_missing_field_invokes_default_method(self) -> None:
        serializer = DefaultFieldMappingSerializer(data={})

        self.assertEqual(serializer.initial_data, {"lastname": "Default lastname"})
        self.assertEqual(serializer.default_calls, 1)

    def test_formatter_receives_explicit_none(self) -> None:
        serializer = FormattingFieldMappingSerializer(data={"external_nullable": None})

        self.assertEqual(serializer.initial_data, {"lastname": None})
        self.assertEqual(serializer.formatted_values, [None])

    def test_formatter_is_not_called_for_missing_field(self) -> None:
        serializer = FormattingFieldMappingSerializer(data={})

        self.assertEqual(serializer.initial_data, {})
        self.assertFalse(hasattr(serializer, "formatted_values"))

    def test_default_is_formatted(self) -> None:
        serializer = DefaultAndFormattingFieldMappingSerializer(data={})

        self.assertEqual(
            serializer.initial_data, {"lastname": "Formatted Default lastname"}
        )

    def test_many_uses_child_defaults_and_formatters(self) -> None:
        serializer = DefaultAndFormattingFieldMappingSerializer(
            data=[{}, {"external_nullable": None}], many=True
        )

        self.assertEqual(
            serializer.initial_data,
            [
                {"lastname": "Formatted Default lastname"},
                {"lastname": "Formatted None"},
            ],
        )

    def test_many_calls_default_once_per_missing_item(self) -> None:
        serializer = DefaultFieldMappingSerializer(
            data=[{}, {"external_nullable": None}, {}], many=True
        )

        self.assertEqual(
            serializer.initial_data,
            [
                {"lastname": "Default lastname"},
                {"lastname": None},
                {"lastname": "Default lastname"},
            ],
        )
        self.assertEqual(serializer.child.default_calls, 2)

    def test_many_calls_formatter_for_present_items_only(self) -> None:
        serializer = FormattingFieldMappingSerializer(
            data=[{}, {"external_nullable": None}, {"external_nullable": "Boss"}],
            many=True,
        )

        self.assertEqual(
            serializer.initial_data,
            [{}, {"lastname": None}, {"lastname": "Boss"}],
        )
        self.assertEqual(serializer.child.formatted_values, [None, "Boss"])

    def test_many_uses_overridden_list_mapping(self) -> None:
        serializer = CustomListMappingSerializer(
            data=[{"external_nullable": "Original lastname"}], many=True
        )

        self.assertEqual(serializer.initial_data, [{"lastname": "Overridden lastname"}])

    def test_invalid_non_mapping_input_is_left_for_drf_validation(self) -> None:
        serializer = NullableFieldMappingSerializer(data=[])

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["non_field_errors"][0].code, "invalid")

    def test_invalid_non_list_many_input_is_left_for_drf_validation(self) -> None:
        serializer = NullableFieldMappingSerializer(data={}, many=True)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["non_field_errors"][0].code, "not_a_list")

    def test_nested_mapping_distinguishes_missing_and_explicit_none(self) -> None:
        serializer = NestedFieldMappingSerializer()

        self.assertEqual(serializer.map_data({}), {})
        self.assertEqual(serializer.map_data({"external": {}}), {})
        self.assertEqual(
            serializer.map_data({"external": {"nested_nullable": None}}),
            {"lastname": None},
        )

    def test_list_mapping_distinguishes_missing_and_explicit_none(self) -> None:
        serializer = NestedFieldMappingSerializer(many=True)

        self.assertEqual(
            serializer.map_list_data(
                [
                    {},
                    {"external": {}},
                    {"external": {"nested_nullable": None}},
                ]
            ),
            [{}, {}, {"lastname": None}],
        )

    def test_update_clears_explicit_nullable_field(self) -> None:
        person = PersonFactory(lastname="Boss")
        serializer = NullableFieldMappingSerializer(
            person, data={"external_nullable": None}
        )

        self.assertTrue(serializer.is_valid(raise_exception=True))
        serializer.save()

        person.refresh_from_db()
        self.assertIsNone(person.lastname)

    def test_update_rejects_explicit_none_for_non_nullable_field(self) -> None:
        person = PersonFactory(firstname="Hugo")
        serializer = NonNullableFieldMappingSerializer(
            person, data={"external_non_nullable": None}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["firstname"][0].code, "null")

        person.refresh_from_db()
        self.assertEqual(person.firstname, "Hugo")

    def test_full_and_partial_updates_preserve_omitted_fields(self) -> None:
        for partial in (False, True):
            with self.subTest(partial=partial):
                person = PersonFactory(lastname="Boss")
                serializer = NullableFieldMappingSerializer(
                    person, data={}, partial=partial
                )

                self.assertTrue(serializer.is_valid(raise_exception=True))
                serializer.save()

                person.refresh_from_db()
                self.assertEqual(person.lastname, "Boss")

    def test_update_rejects_none_for_non_nullable_field_with_model_default(
        self,
    ) -> None:
        message = SystemMessageFactory(order=5)
        serializer = DefaultedModelFieldMappingSerializer(
            message, data={"external_order": None}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["order"][0].code, "null")

        message.refresh_from_db()
        self.assertEqual(message.order, 5)

    def test_update_preserves_omitted_field_with_model_default(self) -> None:
        message = SystemMessageFactory(order=5)
        serializer = DefaultedModelFieldMappingSerializer(message, data={})

        self.assertTrue(serializer.is_valid(raise_exception=True))
        serializer.save()

        message.refresh_from_db()
        self.assertEqual(message.order, 5)

    def test_multiple_nested_relations_keep_their_own_models(self) -> None:
        serializer = MultipleNestedRelationsMappingSerializer(
            data={
                "external_firstname": "Hugo",
                "external_municipality": "Muri",
                "external_person_type": "Employee",
            }
        )

        self.assertEqual(
            serializer.fields["place_of_residence"].model, models.Municipality
        )
        self.assertEqual(serializer.fields["person_type"].model, models.PersonType)
        self.assertTrue(serializer.is_valid(raise_exception=True))

        person = serializer.save()

        self.assertEqual(person.place_of_residence.title, "Muri")
        self.assertIsInstance(person.place_of_residence, models.Municipality)
        self.assertEqual(person.person_type.title, "Employee")
        self.assertIsInstance(person.person_type, models.PersonType)

    def test_many_preserves_nested_relations_for_each_item(self) -> None:
        serializer = MultipleNestedRelationsMappingSerializer(
            data=[
                {
                    "external_firstname": "Hugo",
                    "external_municipality": "Muri",
                    "external_person_type": "Employee",
                },
                {
                    "external_firstname": "Stefanie",
                    "external_municipality": "Bern",
                    "external_person_type": "Volunteer",
                },
            ],
            many=True,
        )

        self.assertTrue(serializer.is_valid(raise_exception=True))
        people = serializer.save()

        self.assertEqual(
            [
                (
                    person.firstname,
                    person.place_of_residence.title,
                    person.person_type.title,
                )
                for person in people
            ],
            [("Hugo", "Muri", "Employee"), ("Stefanie", "Bern", "Volunteer")],
        )

    def test_many_allows_nested_relations_to_be_omitted_per_item(self) -> None:
        serializer = MultipleNestedRelationsMappingSerializer(
            data=[
                {
                    "external_firstname": "Hugo",
                    "external_municipality": "Muri",
                    "external_person_type": "Employee",
                },
                {"external_firstname": "Stefanie"},
            ],
            many=True,
        )

        self.assertTrue(serializer.is_valid(raise_exception=True))
        people = serializer.save()

        self.assertEqual(people[0].place_of_residence.title, "Muri")
        self.assertEqual(people[0].person_type.title, "Employee")
        self.assertIsNone(people[1].place_of_residence)
        self.assertIsNone(people[1].person_type)

    def test_many_rejects_explicit_none_for_nested_non_nullable_field(self) -> None:
        serializer = MultipleNestedRelationsMappingSerializer(
            data=[
                {
                    "external_firstname": "Hugo",
                    "external_municipality": None,
                    "external_person_type": "Employee",
                }
            ],
            many=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors[0]["place_of_residence"]["title"][0].code,
            "null",
        )

    def test_list_mapping_serializer_map_initial_data(self) -> None:
        data = [
            {
                "external_base_field": "base_value",
                "external_single_field_1": "nested_value_1",
                "external_single_field_2": "nested_value_2",
                "external_dict_field": {"nested_field": "single_value"},
                "external_object_field": {
                    "nested_external_field_1": "nested_value_1",
                    "nested_external_field_2": "nested_value_2",
                },
                "external_object_field_with_object": {
                    "external_object_field_1": {
                        "external_field_1": "value_1",
                        "external_field_2": "value_2",
                    },
                    "external_object_field_2": {
                        "external_field_1": "value_1",
                        "external_field_2": "value_2",
                    },
                },
            },
            {
                "external_base_field": "other_value",
                "external_single_field_1": "nested_value_3",
                "external_single_field_2": "nested_value_4",
                "external_dict_field": {"nested_field": "other_value"},
                "external_object_field": {
                    "nested_external_field_1": "nested_value_3",
                    "nested_external_field_2": "nested_value_4",
                },
                "external_object_field_with_object": {
                    "external_object_field_1": {
                        "external_field_1": "value_3",
                        "external_field_2": "value_4",
                    },
                    "external_object_field_2": {
                        "external_field_1": "value_3",
                        "external_field_2": "value_4",
                    },
                },
            },
        ]

        expected_data = [
            {
                "base_field": "base_value",
                "dict_field": {
                    "nested_field_1": "nested_value_1",
                    "nested_field_2": "nested_value_2",
                },
                "single_field": "single_value",
                "object_field": {
                    "nested_field_1": "nested_value_1",
                    "nested_field_2": "nested_value_2",
                },
                "object_field_with_object": {
                    "object_field_1": {"field_1": "value_1", "field_2": "value_2"},
                    "object_field_2": {"field_1": "value_1", "field_2": "value_2"},
                },
            },
            {
                "base_field": "other_value",
                "dict_field": {
                    "nested_field_1": "nested_value_3",
                    "nested_field_2": "nested_value_4",
                },
                "single_field": "other_value",
                "object_field": {
                    "nested_field_1": "nested_value_3",
                    "nested_field_2": "nested_value_4",
                },
                "object_field_with_object": {
                    "object_field_1": {"field_1": "value_3", "field_2": "value_4"},
                    "object_field_2": {"field_1": "value_3", "field_2": "value_4"},
                },
            },
        ]

        serializer = TestMappingSerializer(many=True)
        mapped_data = serializer.map_list_data(data)
        self.assertEqual(mapped_data, expected_data)
