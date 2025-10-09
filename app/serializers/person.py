from typing import Any

from constance import config

from app.models import Person
from app.serializers import BaseMappingSerializer
from django_features.custom_fields.serializers import CustomFieldBaseModelSerializer


class PersonSerializer(CustomFieldBaseModelSerializer):
    class Meta:
        model = Person
        fields = [
            "email",
            "firstname",
            "lastname",
        ]


class PersonMappingSerializer(BaseMappingSerializer):
    class Meta:
        model = Person
        fields = "__all__"

    @property
    def mapping(self) -> dict[str, dict[str, Any]]:
        return config.MODEL_MAPPING_FIELD
