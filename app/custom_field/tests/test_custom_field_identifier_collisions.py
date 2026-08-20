from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

from app.custom_field.models import CustomField
from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.models import Person
from app.models import PersonType
from app.tests import APITestCase
from app.tests.factories import PersonTypeFactory
from django_features.serializers import MappingSerializer


class AliasedPersonSerializer(TypeAwarePersonSerializer):
    display_name = serializers.CharField(source="firstname")

    class Meta(TypeAwarePersonSerializer.Meta):
        fields = [*TypeAwarePersonSerializer.Meta.fields, "display_name"]


class SourceAliasedPersonSerializer(TypeAwarePersonSerializer):
    external_custom = serializers.CharField(source="source_only_custom")

    class Meta(TypeAwarePersonSerializer.Meta):
        fields = [*TypeAwarePersonSerializer.Meta.fields, "external_custom"]


class CollisionMappingSerializer(MappingSerializer):
    class Meta:
        model = Person
        fields = "__all__"

    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return {
            "person": {
                "external_firstname": "firstname",
                "external_email": "email",
            }
        }


class CustomFieldIdentifierCollisionTest(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.person_content_type = ContentType.objects.get_for_model(Person)

    def assert_identifier_rejected(
        self,
        identifier: str,
        *,
        serializer: TypeAwarePersonSerializer | None = None,
    ) -> CustomField:
        custom_field = CustomFieldFactory(
            content_type=self.person_content_type,
            identifier=identifier,
        )
        serializer = serializer or TypeAwarePersonSerializer()

        with self.assertRaisesMessage(ImproperlyConfigured, repr(identifier)):
            serializer.fields

        return custom_field

    def test_concrete_model_field_identifier_is_rejected(self) -> None:
        self.assert_identifier_rejected("email")

    def test_foreign_key_attname_identifier_is_rejected(self) -> None:
        self.assert_identifier_rejected("person_type_id")

    def test_model_methods_and_instance_internals_are_rejected(self) -> None:
        for identifier in (
            "save",
            "_state",
            "_prefetched_objects_cache",
            "handle_custom_values",
        ):
            with self.subTest(identifier=identifier):
                custom_field = self.assert_identifier_rejected(identifier)
                custom_field.delete()

    def test_declared_serializer_alias_identifier_is_rejected(self) -> None:
        self.assert_identifier_rejected(
            "display_name",
            serializer=AliasedPersonSerializer(),
        )

    def test_writable_serializer_source_identifier_is_rejected(self) -> None:
        self.assert_identifier_rejected(
            "source_only_custom",
            serializer=SourceAliasedPersonSerializer(),
        )

    def test_type_specific_collision_is_rejected_for_another_selected_type(
        self,
    ) -> None:
        selected_type = PersonTypeFactory(title="Selected")
        other_type = PersonTypeFactory(title="Other")
        type_content_type = ContentType.objects.get_for_model(PersonType)
        CustomFieldFactory(
            content_type=self.person_content_type,
            identifier="email",
            type_content_type=type_content_type,
            type_id=other_type.pk,
        )
        serializer = TypeAwarePersonSerializer(
            data={"firstname": "Test", "person_type": selected_type.pk}
        )

        with self.assertRaisesMessage(ImproperlyConfigured, "'email'"):
            serializer.is_valid()

    def test_filtered_out_collision_is_still_rejected(self) -> None:
        CustomFieldFactory(
            content_type=self.person_content_type,
            identifier="email",
        )
        serializer = TypeAwarePersonSerializer()
        serializer.filter = {"identifier": "unrelated_custom_field"}

        with self.assertRaisesMessage(ImproperlyConfigured, "'email'"):
            serializer.fields

    def test_excluding_custom_fields_still_rejects_collision(self) -> None:
        CustomFieldFactory(
            content_type=self.person_content_type,
            identifier="email",
        )
        serializer = TypeAwarePersonSerializer(exclude_custom_fields=True)

        with self.assertRaisesMessage(ImproperlyConfigured, "'email'"):
            serializer.fields

    def test_model_manager_rejects_collision_before_building_annotations(
        self,
    ) -> None:
        CustomFieldFactory(
            content_type=self.person_content_type,
            identifier="person_type_id",
        )

        with self.assertRaisesMessage(ImproperlyConfigured, "'person_type_id'"):
            Person.objects.all()

    def test_mapping_create_rejects_collision_before_model_write(self) -> None:
        CustomFieldFactory(
            content_type=self.person_content_type,
            identifier="email",
        )
        serializer = CollisionMappingSerializer(
            data={
                "external_firstname": "Unsafe",
                "external_email": "would-overwrite@example.com",
            }
        )

        with self.assertRaisesMessage(ImproperlyConfigured, "'email'"):
            serializer.is_valid()

        self.assertEqual(Person._base_manager.count(), 0)
