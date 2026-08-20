import json
from collections.abc import Mapping
from typing import Any
from typing import NoReturn

from django.core.exceptions import MultipleObjectsReturned
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.utils.model_meta import get_field_info

from django_features.custom_fields.helpers import get_custom_value_model
from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.value import AbstractBaseCustomValue
from django_features.custom_fields.models.value import CustomValueQuerySet
from django_features.custom_fields.serializers import CustomChoiceSerializer


class ChoiceIdField(serializers.Field):
    _unique_field: str | None = None
    _model_field: models.Field
    default_error_messages = {
        "empty": _("This list may not be empty."),
    }

    def __init__(
        self,
        field: AbstractBaseCustomField,
        unique_field: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.field = field
        self.required = kwargs.get("required", self.field.required)
        self.set_unique_field(unique_field)

    def set_unique_field(self, unique_field: str | None) -> None:
        self._unique_field = unique_field or "id"

        valid_fields = get_field_info(get_custom_value_model()).fields_and_pk
        if self._unique_field not in valid_fields:
            raise ValueError(
                f"The unique_field must be a valid field of {valid_fields}: "
                f"invalid field {self._unique_field}"
            )
        self._model_field = valid_fields[self._unique_field]

    def get_queryset(self) -> CustomValueQuerySet:
        return get_custom_value_model().objects.filter(field_id=self.field.id)

    def to_representation(
        self,
        value: (
            AbstractBaseCustomValue
            | CustomValueQuerySet
            | list[AbstractBaseCustomValue]
        ),
    ) -> dict[str, Any] | list[dict[str, Any]]:
        return CustomChoiceSerializer(value, many=self.field.multiple).data

    def _choice_field(self, data: Any) -> AbstractBaseCustomValue:
        value = self._normalize_choice(data)
        try:
            return self.get_queryset().get(**{self._unique_field: value})
        except MultipleObjectsReturned:
            self._ambiguous([value])
        except (ObjectDoesNotExist, OverflowError, TypeError, ValueError):
            raise ValidationError(
                _("Custom value with the %(field)s %(value)s does not exist.")
                % {"field": self._unique_field, "value": value},
                code="does_not_exist",
            )

    def _ambiguous(self, values: list[Any]) -> NoReturn:
        raise ValidationError(
            _(
                "Multiple custom values match '%(field)s': %(values)s. "
                "Choice lookup values must be unique within a custom field."
            )
            % {"field": self._unique_field, "values": values},
            code="multiple_matches",
        )

    def _malformed(self, data: Any) -> NoReturn:
        raise ValidationError(
            _("Malformed custom choice %(value)r for '%(field)s'.")
            % {"field": self._unique_field, "value": data},
            code="invalid",
        )

    def _normalize_choice(self, data: Any) -> Any:
        if isinstance(data, Mapping):
            if self._unique_field not in data:
                raise ValidationError(
                    _(
                        "Malformed custom choice. Expected a value or object "
                        "containing '%(field)s'."
                    )
                    % {"field": self._unique_field},
                    code="invalid",
                )
            data = data[self._unique_field]

        boolean_fields = (models.BooleanField, models.JSONField)
        if isinstance(data, bool) and not isinstance(self._model_field, boolean_fields):
            self._malformed(data)

        try:
            value = self._model_field.to_python(data)
            self._model_field.get_prep_value(value)
            if isinstance(self._model_field, models.JSONField):
                json.dumps(
                    value,
                    cls=self._model_field.encoder or DjangoJSONEncoder,
                    allow_nan=False,
                )
        except (DjangoValidationError, OverflowError, TypeError, ValueError):
            self._malformed(data)
        return value

    @staticmethod
    def _choice_identity(model_field: models.Field, value: Any) -> tuple[Any, ...]:
        """Return a hashable, type-sensitive identity for a lookup value."""
        if isinstance(model_field, models.JSONField):
            encoder = model_field.encoder or DjangoJSONEncoder
            return (
                "json",
                json.dumps(
                    value,
                    cls=encoder,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )

        prepared = model_field.get_prep_value(value)
        try:
            hash(prepared)
        except TypeError:
            return (type(prepared), repr(prepared))
        return (type(prepared), prepared)

    def _multiple_choice(self, data: list[Any]) -> list[AbstractBaseCustomValue]:
        normalized = [self._normalize_choice(item) for item in data]
        identities = [
            self._choice_identity(self._model_field, value) for value in normalized
        ]

        duplicate_indexes: list[int] = []
        seen: set[tuple[Any, ...]] = set()
        for index, identity in enumerate(identities):
            if identity in seen:
                duplicate_indexes.append(index)
            seen.add(identity)
        duplicates = [normalized[index] for index in duplicate_indexes]
        if duplicates:
            raise ValidationError(
                _("Duplicate custom choice values are not allowed: %(values)s")
                % {"values": duplicates},
                code="duplicate",
            )

        if not normalized:
            return []

        queryset = self.get_queryset()
        if isinstance(self._model_field, models.JSONField):
            # JSON ``__in`` coerces mixed boolean/numeric values to one database
            # type on PostgreSQL. Exact OR lookups retain their JSON identities.
            lookup = Q()
            for value in normalized:
                lookup |= Q(**{self._unique_field: value})
            queryset = queryset.filter(lookup)
        else:
            queryset = queryset.filter(**{f"{self._unique_field}__in": normalized})
        matches = list(queryset)
        matches_by_identity: dict[tuple[Any, ...], list[AbstractBaseCustomValue]] = {}
        for match in matches:
            raw_value = self._model_field.value_from_object(match)
            match_identity = self._choice_identity(self._model_field, raw_value)
            matches_by_identity.setdefault(match_identity, []).append(match)

        ambiguous = [
            value
            for value, identity in zip(normalized, identities, strict=True)
            if len(matches_by_identity.get(identity, ())) > 1
        ]
        if ambiguous:
            self._ambiguous(ambiguous)

        missing = [
            value
            for value, identity in zip(normalized, identities, strict=True)
            if identity not in matches_by_identity
        ]
        if missing:
            raise ValidationError(
                _("Some custom choices do not exist for '%(field)s': %(values)s")
                % {"field": self._unique_field, "values": missing},
                code="does_not_exist",
            )
        return [matches_by_identity[identity][0] for identity in identities]

    def to_internal_value(
        self, data: Any
    ) -> AbstractBaseCustomValue | list[AbstractBaseCustomValue]:
        if not self.field.choice_field:
            raise ValidationError(
                _("The field %(field)s is not a choice field.") % {"field": self.field},
                code="not_choice",
            )
        if self.field.multiple:
            if not isinstance(data, list):
                raise ValidationError(
                    _("Expected a list of custom choices, but got %(value)r.")
                    % {"value": data},
                    code="not_a_list",
                )
            if not data and not self.field.allow_blank:
                raise ValidationError(self.error_messages["empty"], code="empty")
            return self._multiple_choice(data)
        return self._choice_field(data)
