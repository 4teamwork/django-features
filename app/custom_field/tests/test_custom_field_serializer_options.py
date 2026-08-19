from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.tests import APITestCase


class CustomFieldSerializerConstructorTest(APITestCase):
    def setUp(self) -> None:
        CustomFieldFactory(identifier="custom_value")

    def test_exclude_custom_fields_constructor_option_is_not_passed_to_drf(
        self,
    ) -> None:
        serializer = TypeAwarePersonSerializer(exclude_custom_fields=True)

        self.assertTrue(serializer.exclude_custom_fields)
        self.assertNotIn("custom_value", serializer.fields)

    def test_write_only_serializer_constructor_option_is_not_passed_to_drf(
        self,
    ) -> None:
        serializer = TypeAwarePersonSerializer(write_only_serializer=True)

        self.assertTrue(serializer.write_only_serializer)

    def test_constructor_options_keep_class_defaults(self) -> None:
        serializer = TypeAwarePersonSerializer()

        self.assertFalse(serializer.exclude_custom_fields)
        self.assertFalse(serializer.write_only_serializer)

    def test_constructor_options_are_preserved_for_every_list_item(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data=[{"firstname": "First"}, {"firstname": "Second"}],
            many=True,
            exclude_custom_fields=True,
            write_only_serializer=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.child.exclude_custom_fields)
        self.assertTrue(serializer.child.write_only_serializer)
        self.assertTrue(
            all(
                item.exclude_custom_fields and item.write_only_serializer
                for item in serializer._validated_item_serializers
            )
        )
