from typing import Any

from app import models
from app.tests import APITestCase
from django_features.serializers import MappingSerializer


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
