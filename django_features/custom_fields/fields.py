import json
import reprlib
from collections.abc import Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ChoiceLookupMetadata:
    field_name: str
    model_field: models.Field


@dataclass(frozen=True)
class _SafeChoiceValue:
    """Render malformed recursive or deeply nested values without raising."""

    value: Any

    def __repr__(self) -> str:
        try:
            return reprlib.repr(self.value)
        except Exception:  # pragma: no cover - defensive against hostile repr hooks
            return f"<{type(self.value).__name__}>"


def _normalize_postgresql_json_value(value: Any) -> Any:
    """Return the value as PostgreSQL can represent it in ``jsonb``.

    PostgreSQL rejects U+0000 and unpaired UTF-16 surrogate code points while
    parsing JSON and canonicalizes negative numeric zero to positive zero. Apply
    those rules before constructing a lookup so malformed input becomes a field
    error and valid stored values retain a reachable identity.
    """

    if isinstance(value, str):
        if "\x00" in value or any(
            0xD800 <= ord(character) <= 0xDFFF for character in value
        ):
            raise ValueError("PostgreSQL jsonb does not support this string.")
        return value
    if isinstance(value, float) and value == 0:
        return 0.0
    if isinstance(value, list):
        return [_normalize_postgresql_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            _normalize_postgresql_json_value(key): _normalize_postgresql_json_value(
                item
            )
            for key, item in value.items()
        }
    return value


def _canonical_json_choice(
    model_field: models.JSONField,
    value: Any,
) -> tuple[Any, str]:
    """Return a PostgreSQL-compatible value and its canonical JSON identity.

    Encoding and decoding first applies the configured Django encoder and mirrors
    JSON object-key coercion, including PostgreSQL's last-key-wins behavior.  The
    second encoding is stable for identity and duplicate comparisons.
    """

    encoded = json.dumps(
        value,
        cls=model_field.encoder or DjangoJSONEncoder,
        allow_nan=False,
    )
    normalized = _normalize_postgresql_json_value(json.loads(encoded))
    identity = json.dumps(
        normalized,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return normalized, identity


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
        self._valid_lookup_fields = get_field_info(
            get_custom_value_model()
        ).fields_and_pk
        self.set_unique_field(unique_field)

    def _get_lookup_metadata(
        self,
        unique_field: str | None,
    ) -> ChoiceLookupMetadata:
        field_name = unique_field or "id"
        if field_name not in self._valid_lookup_fields:
            raise ValueError(
                "The unique_field must be a valid field of "
                f"{self._valid_lookup_fields}: invalid field {field_name}"
            )
        return ChoiceLookupMetadata(
            field_name=field_name,
            model_field=self._valid_lookup_fields[field_name],
        )

    def set_unique_field(self, unique_field: str | None) -> None:
        lookup = self._get_lookup_metadata(unique_field)
        self._request_lookup = lookup
        # Keep these public implementation attributes for compatibility with
        # serializers which configure or inspect the request lookup.
        self._unique_field = lookup.field_name
        self._model_field = lookup.model_field

    def get_queryset(self) -> CustomValueQuerySet:
        return get_custom_value_model().objects.filter(field_id=self.field.id)

    def run_default_validation(
        self, data: Any
    ) -> AbstractBaseCustomValue | list[AbstractBaseCustomValue]:
        """Validate configured defaults as canonical custom-value primary keys.

        Request payloads continue to use the lookup selected by the serializer,
        such as ``value`` for mapping serializers.  Defaults are stored in the
        custom-field definition itself, so they must have one stable format
        independent of the serializer which happens to apply them.
        """
        is_empty, value = self.validate_empty_values(data)
        if is_empty:
            return value
        validated = self._to_internal_value(
            value,
            lookup=self._get_lookup_metadata("pk"),
        )
        self.run_validators(validated)
        return validated

    def to_representation(
        self,
        value: (
            AbstractBaseCustomValue
            | CustomValueQuerySet
            | list[AbstractBaseCustomValue]
        ),
    ) -> dict[str, Any] | list[dict[str, Any]]:
        return CustomChoiceSerializer(value, many=self.field.multiple).data

    def _choice_field(
        self,
        data: Any,
        *,
        lookup: ChoiceLookupMetadata | None = None,
    ) -> AbstractBaseCustomValue:
        lookup = lookup or self._request_lookup
        value = self._normalize_choice(data, lookup=lookup)
        try:
            if isinstance(lookup.model_field, models.JSONField):
                identity = self._choice_identity(lookup.model_field, value)
                matches = [
                    match
                    for match in self.get_queryset().filter(
                        **{lookup.field_name: value}
                    )
                    if self._choice_identity(
                        lookup.model_field,
                        lookup.model_field.value_from_object(match),
                    )
                    == identity
                ]
                if len(matches) > 1:
                    self._ambiguous([value], lookup=lookup)
                if matches:
                    return matches[0]
                raise ObjectDoesNotExist
            return self.get_queryset().get(**{lookup.field_name: value})
        except MultipleObjectsReturned:
            self._ambiguous([value], lookup=lookup)
        except (ObjectDoesNotExist, OverflowError, TypeError, ValueError):
            raise ValidationError(
                _("Custom value with the %(field)s %(value)s does not exist.")
                % {"field": lookup.field_name, "value": value},
                code="does_not_exist",
            )

    def _ambiguous(
        self,
        values: list[Any],
        *,
        lookup: ChoiceLookupMetadata | None = None,
    ) -> NoReturn:
        lookup = lookup or self._request_lookup
        raise ValidationError(
            _(
                "Multiple custom values match '%(field)s': %(values)s. "
                "Choice lookup values must be unique within a custom field."
            )
            % {"field": lookup.field_name, "values": values},
            code="multiple_matches",
        )

    def _malformed(
        self,
        data: Any,
        *,
        lookup: ChoiceLookupMetadata | None = None,
    ) -> NoReturn:
        lookup = lookup or self._request_lookup
        raise ValidationError(
            _("Malformed custom choice %(value)r for '%(field)s'.")
            % {"field": lookup.field_name, "value": _SafeChoiceValue(data)},
            code="invalid",
        )

    def _normalize_choice(
        self,
        data: Any,
        *,
        lookup: ChoiceLookupMetadata | None = None,
    ) -> Any:
        lookup = lookup or self._request_lookup
        if isinstance(data, Mapping):
            if lookup.field_name not in data:
                raise ValidationError(
                    _(
                        "Malformed custom choice. Expected a value or object "
                        "containing '%(field)s'."
                    )
                    % {"field": lookup.field_name},
                    code="invalid",
                )
            data = data[lookup.field_name]

        boolean_fields = (models.BooleanField, models.JSONField)
        if isinstance(data, bool) and not isinstance(
            lookup.model_field,
            boolean_fields,
        ):
            self._malformed(data, lookup=lookup)

        try:
            value = lookup.model_field.to_python(data)
            lookup.model_field.get_prep_value(value)
            if isinstance(lookup.model_field, models.JSONField):
                value, _identity = _canonical_json_choice(lookup.model_field, value)
        except (
            DjangoValidationError,
            OverflowError,
            RecursionError,
            TypeError,
            ValueError,
        ):
            self._malformed(data, lookup=lookup)
        return value

    @staticmethod
    def _choice_identity(model_field: models.Field, value: Any) -> tuple[Any, ...]:
        """Return a hashable, type-sensitive identity for a lookup value."""
        if isinstance(model_field, models.JSONField):
            _normalized, identity = _canonical_json_choice(model_field, value)
            return (
                "json",
                identity,
            )

        prepared = model_field.get_prep_value(value)
        try:
            hash(prepared)
        except TypeError:
            return (type(prepared), repr(prepared))
        return (type(prepared), prepared)

    def _multiple_choice(
        self,
        data: list[Any],
        *,
        lookup: ChoiceLookupMetadata | None = None,
    ) -> list[AbstractBaseCustomValue]:
        lookup = lookup or self._request_lookup
        normalized = [self._normalize_choice(item, lookup=lookup) for item in data]
        identities = [
            self._choice_identity(lookup.model_field, value) for value in normalized
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
        if isinstance(lookup.model_field, models.JSONField):
            # JSON ``__in`` coerces mixed boolean/numeric values to one database
            # type on PostgreSQL. Exact OR lookups retain their JSON identities.
            query = Q()
            for value in normalized:
                query |= Q(**{lookup.field_name: value})
            queryset = queryset.filter(query)
        else:
            queryset = queryset.filter(**{f"{lookup.field_name}__in": normalized})
        matches = list(queryset)
        matches_by_identity: dict[tuple[Any, ...], list[AbstractBaseCustomValue]] = {}
        for match in matches:
            raw_value = lookup.model_field.value_from_object(match)
            match_identity = self._choice_identity(lookup.model_field, raw_value)
            matches_by_identity.setdefault(match_identity, []).append(match)

        ambiguous = [
            value
            for value, identity in zip(normalized, identities, strict=True)
            if len(matches_by_identity.get(identity, ())) > 1
        ]
        if ambiguous:
            self._ambiguous(ambiguous, lookup=lookup)

        missing = [
            value
            for value, identity in zip(normalized, identities, strict=True)
            if identity not in matches_by_identity
        ]
        if missing:
            raise ValidationError(
                _("Some custom choices do not exist for '%(field)s': %(values)s")
                % {"field": lookup.field_name, "values": missing},
                code="does_not_exist",
            )
        return [matches_by_identity[identity][0] for identity in identities]

    def _to_internal_value(
        self,
        data: Any,
        *,
        lookup: ChoiceLookupMetadata,
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
            return self._multiple_choice(data, lookup=lookup)
        return self._choice_field(data, lookup=lookup)

    def to_internal_value(
        self, data: Any
    ) -> AbstractBaseCustomValue | list[AbstractBaseCustomValue]:
        return self._to_internal_value(data, lookup=self._request_lookup)
