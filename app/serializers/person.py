from typing import Any

from constance import config

from app.models import Person
from app.serializers import BaseMappingSerializer
from django_features.custom_fields.serializers import CustomFieldBaseModelSerializer
from django_features.fields import ExternalUUIDRelatedField
from django_features.fields import RelatedField


class PersonSerializer(CustomFieldBaseModelSerializer):
    class Meta:
        model = Person
        fields = [
            "email",
            "firstname",
            "lastname",
        ]


class PersonMappingSerializer(BaseMappingSerializer):
    serializer_related_fields = {"addresses": ExternalUUIDRelatedField}

    election_district = RelatedField(
        related_field_name="title", allow_null=True, creation=False, required=False
    )

    class Meta:
        model = Person
        fields = "__all__"

    @property
    def mapping(self) -> dict[str, dict[str, Any]]:
        return config.MODEL_MAPPING_FIELD
