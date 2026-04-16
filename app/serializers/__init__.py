from typing import Any

from constance import config

from django_features.serializers import MappingSerializer


class BaseMappingSerializer(MappingSerializer):
    @property  # type: ignore[misc]
    def mapping(self) -> dict[str, dict[str, Any]]:
        return config.MODEL_MAPPING_FIELD
