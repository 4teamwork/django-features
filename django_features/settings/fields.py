import json
from typing import Any

from django.forms import fields

from django_features.validations import MappingValidationMixin


class PrettyJSONEncoder(json.JSONEncoder):
    def __init__(self, *args: Any, indent: int, sort_keys: bool, **kwargs: Any) -> None:
        super().__init__(*args, indent=2, **kwargs)


class PrettyJSONField(fields.JSONField):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["encoder"] = PrettyJSONEncoder
        super().__init__(*args, **kwargs)


class ModelFieldMapping(MappingValidationMixin, PrettyJSONField):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def validate(self, value: Any) -> None:
        super().validate(value)
        if value is None:
            return
        self.validate_models_field_mapping(value)
