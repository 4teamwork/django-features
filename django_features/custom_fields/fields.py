from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from pluck import pluck
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

    def to_representation(
        self, value: CustomValue | CustomValueQuerySet
    ) -> int | list[int]:
        return CustomChoiceSerializer(value, many=self.field.multiple).data

    def _choice_field(self, data: int | str | dict) -> CustomValue:
        if isinstance(data, dict):
            value = data.get("id")
        else:
            value = data
        try:
            return self.get_queryset().get(**{self._unique_field: value})
        except ObjectDoesNotExist:
            raise ValidationError(
                f"Custom value with the {self._unique_field} {data} does not exist."
            )

    def _multiple_choice(self, data: list[int | str | dict]) -> CustomValueQuerySet:
        if all(type(d) is dict for d in data):
            value = pluck(data, self._unique_field)
        else:
            value = data
        values = self.get_queryset().filter(**{f"{self._unique_field}__in": value})
        if values.count() != len(data):
            missing = set(data) - set(values.values_list(self._unique_field, flat=True))
            raise ValidationError(
                f"Some of the given {self._unique_field}s do not match: {missing}"
            )
        return values

    def to_internal_value(self, data: Any) -> CustomValue | CustomValueQuerySet:
        if self.field.multiple and isinstance(data, list):
            return self._multiple_choice(data)
        elif self.field.choice_field and isinstance(data, (int, str, dict)):
            return self._choice_field(data)
        else:
            if not self.field.choice_field:
                raise ValidationError(f"The field {self.field} is not a choice field.")
            raise ValidationError(
                f"The given value {data} has not a valid type. Expected a list or int."
            )
