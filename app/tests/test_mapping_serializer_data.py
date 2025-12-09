from typing import Any

from app import models
from app.tests import APITestCase
from django_features.serializers import MappingSerializer


class TestMappingSerializer(MappingSerializer):
    class Meta:
        model = models.Person
        fields = "__all__"

    @property
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
