from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django_features.custom_fields.models import CustomValue


class ChoiceIdField(serializers.Field):
    def to_internal_value(self, data: Any) -> CustomValue:
        if isinstance(data, int):
            try:
                return CustomValue.objects.get(id=data)
            except ObjectDoesNotExist:
                raise ValidationError(
                    f"Custom value with the id {data} does not exist."
                )
        elif isinstance(data, list):
            values = CustomValue.objects.filter(id__in=data)
            if values.count() != len(data):
                missing = set(data) - set(values.values_list("id", flat=True))
                raise ValidationError(f"Some of the given ids do not match: {missing}")
            return values
        raise ValidationError(
            f"The given value {data} has not a valid type. Expected a list or int."
        )
