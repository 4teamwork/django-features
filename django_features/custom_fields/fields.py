from collections.abc import Iterable
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from rest_framework import serializers
from rest_framework.utils.model_meta import get_field_info

from django_features.custom_fields.helpers import get_custom_value_model
from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.field import warn_invalid_default
from django_features.custom_fields.models.value import AbstractBaseCustomValue
from django_features.custom_fields.serializers import CustomChoiceSerializer


class ChoiceIdField(serializers.Field):
    default_error_messages = {
        "shape": "Expected a list for multiple choices or a scalar for a single choice.",
        "invalid": "Invalid choice lookup value.",
        "missing": "A selected choice does not exist in this field.",
        "duplicate": "A choice may only be selected once.",
        "ambiguous": "More than one choice matches the lookup value.",
        "empty": "This list may not be empty.",
        "blank": "This field may not be blank.",
        "not_choice": "This field is not a choice field.",
    }

    def __init__(
        self,
        field: AbstractBaseCustomField,
        unique_field: str | None = None,
        choices: Iterable[AbstractBaseCustomValue] | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("required", field.required)
        kwargs.setdefault("allow_null", field.allow_null)
        super().__init__(**kwargs)
        self.field = field
        self._supplied_choices = choices
        self._choices: list[AbstractBaseCustomValue] | None = None
        self._invalid_default = False
        self.set_unique_field(unique_field)

    def set_unique_field(self, unique_field: str | None) -> None:
        self._lookup_field = unique_field or "id"
        model = get_custom_value_model()
        valid_fields = get_field_info(model).fields_and_pk
        if unique_field is None:
            self._model_field = model._meta.pk
        elif self._lookup_field in valid_fields:
            self._model_field = valid_fields[self._lookup_field]
        elif self._lookup_field == "id":
            self._model_field = model._meta.pk
        else:
            raise ValueError(f"Invalid unique_field: {self._lookup_field}")
        self._indexes: dict[str, dict[Any, list[AbstractBaseCustomValue]]] = {}

    def get_default(
        self,
    ) -> AbstractBaseCustomValue | list[AbstractBaseCustomValue] | None:
        value = super().get_default()
        if self._invalid_default:
            raise serializers.SkipField()
        # Configuration stores canonical IDs, independently of a client's lookup key.
        try:
            return self._resolve(value, "pk", get_custom_value_model()._meta.pk)
        except serializers.ValidationError:
            self._invalid_default = True
            warn_invalid_default(self.field)
            raise serializers.SkipField() from None

    def _key(self, value: Any, model_field: models.Field) -> Any:
        try:
            hash(value)
            if (
                model_field.primary_key
                and isinstance(model_field, models.IntegerField)
                and (value is None or isinstance(value, (bool, float)))
            ):
                self.fail("invalid")
            normalized = model_field.to_python(value)
            hash(normalized)
            return type(normalized), normalized
        except (DjangoValidationError, TypeError, ValueError):
            self.fail("invalid")

    def _lookup_key(
        self, data: Any, lookup_field: str, model_field: models.Field
    ) -> Any:
        if isinstance(data, dict):
            if lookup_field in data:
                value = data[lookup_field]
            elif "id" in data:
                value = data["id"]
            else:
                self.fail("invalid")
        else:
            value = data
        if value == "" and not self.field.allow_blank:
            self.fail("blank")
        return self._key(value, model_field)

    def _get_choices(self) -> list[AbstractBaseCustomValue]:
        if self._choices is None:
            source = (
                self.field.choices
                if self._supplied_choices is None
                else self._supplied_choices
            )
            self._choices = list(source)
        return self._choices

    def _get_index(
        self, model_field: models.Field
    ) -> dict[Any, list[AbstractBaseCustomValue]]:
        if model_field.name not in self._indexes:
            index: dict[Any, list[AbstractBaseCustomValue]] = {}
            for choice in self._get_choices():
                if choice.field_id != self.field.id:
                    self.fail("invalid")
                index.setdefault(
                    self._key(getattr(choice, model_field.name), model_field), []
                ).append(choice)
            self._indexes[model_field.name] = index
        return self._indexes[model_field.name]

    def to_representation(self, value: Any) -> dict | list | None:
        if value is None:
            return None
        return CustomChoiceSerializer(value, many=self.field.multiple).data

    def to_internal_value(
        self, data: Any
    ) -> AbstractBaseCustomValue | list[AbstractBaseCustomValue] | None:
        return self._resolve(data, self._lookup_field, self._model_field)

    def _resolve(
        self, data: Any, lookup_field: str, model_field: models.Field
    ) -> AbstractBaseCustomValue | list[AbstractBaseCustomValue] | None:
        if not self.field.choice_field:
            self.fail("not_choice")
        if data is None:
            if self.allow_null:
                return None
            self.fail("null")
        if self.field.multiple != isinstance(data, list):
            self.fail("shape")
        values = data if self.field.multiple else [data]
        if not values and not self.field.allow_blank:
            self.fail("empty")
        keys = [self._lookup_key(item, lookup_field, model_field) for item in values]
        if len(set(keys)) != len(keys):
            self.fail("duplicate")
        index = self._get_index(model_field)
        selected = []
        for key in keys:
            matches = index.get(key, [])
            if not matches:
                self.fail("missing")
            if len(matches) > 1:
                self.fail("ambiguous")
            selected.append(matches[0])
        if not self.field.multiple:
            return selected[0]
        # Preserve catalog ordering while returning a fresh collection for each selection.
        selected_ids = {choice.pk for choice in selected}
        return [choice for choice in self._get_choices() if choice.pk in selected_ids]
