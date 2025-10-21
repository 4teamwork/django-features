from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.utils.model_meta import get_field_info

from django_features.custom_fields.models import CustomField
from django_features.custom_fields.models import CustomValue
from django_features.custom_fields.models.value import CustomValueQuerySet
from django_features.custom_fields.serializers import CustomChoiceSerializer


class ChoiceIdField(serializers.Field):
    _unique_field: str | None = None

    def __init__(
        self, field: CustomField, unique_field: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.field = field
        self.required = kwargs.get("required", self.field.required)
        self.set_unique_field(unique_field)

    def set_unique_field(self, unique_field: str | None) -> None:
        self._unique_field = unique_field or "id"

        valid_fields = get_field_info(CustomValue).fields_and_pk
        if self._unique_field not in valid_fields:
            raise ValueError(
                f"The unique_field must be a valid field of {valid_fields}: invalid field {self.unique_field}"
            )

    def get_queryset(self) -> CustomValueQuerySet:
        return CustomValue.objects.filter(field_id=self.field.id)

    def to_internal_value(self, data: Any) -> CustomValue | CustomValueQuerySet:
        qs = self.get_queryset()
        if isinstance(data, int) or isinstance(data, str):
            try:
                return qs.get(**{self.unique_field: data})
            except ObjectDoesNotExist:
                raise ValidationError(
                    f"Custom value with the {self.unique_field} {data} does not exist."
                )
        elif isinstance(data, list):
            values = qs.filter(**{f"{self.unique_field}__in": data})
            if values.count() != len(data):
                missing = set(data) - set(
                    values.values_list(self.unique_field, flat=True)
                )
                raise ValidationError(
                    f"Some of the given {self.unique_field}s do not match: {missing}"
                )
            return values
        raise ValidationError(
            f"The given value {data} has not a valid type. Expected a list or int."
        )
    def to_representation(
        self, value: CustomValue | CustomValueQuerySet
    ) -> int | list[int]:
        return CustomChoiceSerializer(value, many=self.field.multiple_choice).data

