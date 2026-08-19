from django.db.models import QuerySet
from rest_framework import serializers

from app.custom_field.models import CustomField
from app.models import Person
from app.models import PersonType
from django_features.custom_fields.serializers import CustomFieldBaseModelSerializer


class TypeAwarePersonSerializer(CustomFieldBaseModelSerializer):
    class Meta:
        model = Person
        fields = ["email", "firstname", "lastname", "person_type"]


class TypeIdPersonSerializer(CustomFieldBaseModelSerializer):
    custom_field_type_input_field = "type_id"

    type_id = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=PersonType.objects.all(),
        required=False,
        source="person_type",
    )

    class Meta:
        model = Person
        fields = ["email", "firstname", "lastname", "type_id"]


class HookedPersonSerializer(TypeAwarePersonSerializer):
    def get_custom_fields_queryset(self) -> QuerySet:
        return super().get_custom_fields_queryset().filter(identifier="included")


class TrustedPersonSerializer(TypeAwarePersonSerializer):
    def is_custom_field_writable(self, custom_field: CustomField) -> bool:
        return custom_field.identifier in self.context.get("trusted_fields", ())
