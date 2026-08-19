import copy
from collections import namedtuple
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from typing import Hashable

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.fields import SkipField

from django_features.custom_fields.helpers import get_custom_field_model
from django_features.custom_fields.helpers import get_custom_value_model
from django_features.custom_fields.models.base import CustomFieldBaseModel
from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.field import ValidatedCustomFieldDefault
from django_features.custom_fields.models.value import AbstractBaseCustomValue


class CustomChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_custom_value_model()
        fields = ["id", "label", "value"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if isinstance(self.instance, AbstractBaseCustomValue):
            field = self.instance.field
            self.fields["value"] = get_custom_field_model().TYPE_SERIALIZER_MAP[
                field.field_type
            ](allow_null=True, read_only=True, required=False)


class CustomFieldSerializer(serializers.ModelSerializer):
    choices = serializers.SerializerMethodField()

    class Meta:
        model = get_custom_field_model()
        fields = [
            "choice_field",
            "choices",
            "allow_blank",
            "allow_null",
            "created",
            "default",
            "editable",
            "external_key",
            "field_type",
            "hidden",
            "id",
            "identifier",
            "label",
            "modified",
            "multiple",
            "order",
            "filterable",
            "required",
            "type_content_type",
            "type_id",
        ]

    def get_choices(self, obj: AbstractBaseCustomField) -> list:
        return CustomChoiceSerializer(obj.choices, many=True).data


CustomFieldData = namedtuple(
    "CustomFieldData",
    [
        "id",
        "identifier",
        "choices",
        "choice_field",
        "multiple",
        "serializer_field",
        "custom_field",
    ],
)


@dataclass
class CustomFieldDefinitionCache:
    fields_by_type: dict[Hashable | None, list[AbstractBaseCustomField]]
    identifiers_by_filter: dict[Hashable, set[str]]


@dataclass(frozen=True)
class CustomFieldTypeSelection:
    input_field: str
    source: str
    type_id: int | None
    must_be_present: bool
    resolved: bool = True


class CustomFieldListSerializer(serializers.ListSerializer):
    """Use a dedicated child serializer for every list item.

    Dynamic custom fields depend on an item's configured type. DRF normally reuses
    one child serializer for an entire list, which cannot represent or validate a
    heterogeneous list correctly.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._custom_field_definition_cache = CustomFieldDefinitionCache({}, {})
        self.child._custom_field_definition_cache = self._custom_field_definition_cache
        self._validated_item_serializers: list[CustomFieldBaseModelSerializer] = []

    def to_internal_value(self, data: Any) -> list[Any]:
        self._validated_item_serializers = []
        return super().to_internal_value(data)

    def run_child_validation(self, data: Any) -> Any:
        serializer = self.child.for_item(data=data)
        self._validated_item_serializers.append(serializer)
        return serializer.run_validation(data)

    def create(self, validated_data: list[dict[str, Any]]) -> list[Any]:
        if len(self._validated_item_serializers) != len(validated_data):
            raise AssertionError(
                "List validation changed the number of custom-field serializer "
                "items. Override create() to define how they should be matched."
            )
        return [
            serializer.create(attrs)
            for serializer, attrs in zip(
                self._validated_item_serializers, validated_data, strict=True
            )
        ]

    def to_representation(self, data: Any) -> list[Any]:
        if data is getattr(self, "_validated_data", None):
            if len(self._validated_item_serializers) != len(data):
                raise AssertionError(
                    "List validation changed the number of custom-field serializer "
                    "items. Override to_representation() to define how they should "
                    "be matched."
                )
            return [
                serializer.to_representation(item)
                for serializer, item in zip(
                    self._validated_item_serializers, data, strict=True
                )
            ]

        iterable = data.all() if isinstance(data, models.manager.BaseManager) else data
        return [
            self.child.for_item(instance=item).to_representation(item)
            for item in iterable
        ]


class CustomFieldBaseModelSerializer(serializers.ModelSerializer):
    _exclude_custom_fields = False
    _custom_fields: list[CustomFieldData]
    _unique_choice_field = "id"
    _write_only_serializer = False
    custom_field_type_input_field: str | None = None

    class Meta:
        abstract = True
        fields = "__all__"
        model = None

    def __init__(
        self,
        instance: Any = None,
        data: Any = empty,
        **kwargs: Any,
    ) -> None:
        self._item_serializer_kwargs = dict(kwargs)
        self._custom_field_type_selection: CustomFieldTypeSelection | None = None
        self._custom_field_type_resolution_failed = False
        self._custom_field_type_resolved = False
        self._resolved_custom_field_type_id: int | None = None
        self._custom_fields = []
        self._all_custom_field_identifiers: set[str] = set()
        self._all_custom_field_identifiers_resolved = False
        self._custom_field_definition_cache: CustomFieldDefinitionCache | None = (
            kwargs.pop("_custom_field_definition_cache", None)
        )
        self.exclude_custom_fields: bool = kwargs.pop(
            "exclude_custom_fields", self._exclude_custom_fields
        )
        self._filter: dict[str, Any] = {}
        self.write_only_serializer = kwargs.pop(
            "write_only_serializer", self._write_only_serializer
        )
        if self.custom_field_type_input_field is None:
            self.custom_field_type_input_field = getattr(
                self.Meta.model, "_custom_field_type_attr", None
            )
        super().__init__(instance, data, **kwargs)

    @classmethod
    def many_init(cls, *args: Any, **kwargs: Any) -> serializers.ListSerializer:
        """Use the custom list serializer unless a subclass explicitly replaces it."""
        list_kwargs: dict[str, Any] = {}
        for key in serializers.LIST_SERIALIZER_KWARGS_REMOVE:
            value = kwargs.pop(key, None)
            if value is not None:
                list_kwargs[key] = value
        list_kwargs["child"] = cls(*args, **kwargs)
        list_kwargs.update(
            {
                key: value
                for key, value in kwargs.items()
                if key in serializers.LIST_SERIALIZER_KWARGS
            }
        )
        meta = getattr(cls, "Meta", None)
        list_serializer_class = getattr(
            meta, "list_serializer_class", CustomFieldListSerializer
        )
        return list_serializer_class(*args, **list_kwargs)

    @property
    def model(self) -> models.Model:
        if not self.Meta.model:
            raise ValueError("Meta.model must be set")
        return self.Meta.model

    @property
    def filter(self) -> dict[str, Any]:
        return self._filter

    @filter.setter
    def filter(self, value: dict[str, Any]) -> None:
        self._filter = value

    def get_fields(self) -> dict[str, Any]:
        fields = super().get_fields()
        self._static_serializer_fields = dict(fields)
        if self.exclude_custom_fields:
            return fields
        self._custom_fields = []
        cache = self._custom_field_definition_cache
        cache_key = self.get_custom_fields_cache_key()
        if cache is not None and cache_key in cache.fields_by_type:
            custom_fields = cache.fields_by_type[cache_key]
        else:
            custom_fields = list(self.get_custom_fields_queryset())
            if cache is not None:
                cache.fields_by_type[cache_key] = custom_fields

        self._all_custom_field_identifiers = self.get_all_custom_field_identifiers()
        for field in custom_fields:
            try:
                serialized_field = field.serializer_field
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({field.identifier: exc.detail})
            if not self.is_custom_field_writable(field):
                # Server-managed fields are never required client input. Keep
                # their configured default for creates even when the custom-field
                # definition itself is marked as required.
                serialized_field.required = False
                if field.default is not None:
                    serialized_field.default = ValidatedCustomFieldDefault(
                        field.default
                    )
            if isinstance(self.instance, self.model):
                # Custom-field defaults are create-only. Both full and partial
                # updates preserve every omitted custom value.
                serialized_field.default = empty
            if field.choice_field:
                serialized_field.set_unique_field(self._unique_choice_field)
            self._custom_fields.append(
                CustomFieldData(
                    field.id,
                    field.identifier,
                    field.choices,
                    field.choice_field,
                    field.multiple,
                    serialized_field,
                    field,
                )
            )
            fields[field.identifier] = serialized_field
        return fields

    def get_all_custom_field_identifiers(self) -> set[str]:
        if self._all_custom_field_identifiers_resolved:
            return self._all_custom_field_identifiers

        filter_key = tuple(
            sorted((key, repr(value)) for key, value in self.filter.items())
        )
        cache = self._custom_field_definition_cache
        if cache is not None and filter_key in cache.identifiers_by_filter:
            identifiers = cache.identifiers_by_filter[filter_key]
        else:
            identifiers = set(
                get_custom_field_model()
                .objects.for_model(self.model)
                .filter(**self.filter)
                .values_list("identifier", flat=True)
            )
            if cache is not None:
                cache.identifiers_by_filter[filter_key] = identifiers

        self._all_custom_field_identifiers = identifiers
        self._all_custom_field_identifiers_resolved = True
        return identifiers

    def is_known_custom_field_identifier(self, identifier: str) -> bool:
        return identifier in self.get_all_custom_field_identifiers()

    def get_custom_field_type_input_field(self) -> str | None:
        return self.custom_field_type_input_field

    def get_custom_fields_cache_key(self) -> Hashable | None:
        """Return the per-list cache key for the applicable custom fields."""
        filter_key = tuple(
            sorted((key, repr(value)) for key, value in self.filter.items())
        )
        return self.get_custom_field_type_id(), filter_key

    def for_item(
        self, instance: Any = None, data: Any = empty
    ) -> "CustomFieldBaseModelSerializer":
        """Return an unbound serializer configured for one list item.

        Serializers with additional constructor arguments can override this method
        and pass those arguments while retaining the shared definition cache.
        """
        kwargs = dict(self._item_serializer_kwargs)
        kwargs.update(
            {
                "context": self.context,
                "partial": self.partial,
                "exclude_custom_fields": self.exclude_custom_fields,
                "write_only_serializer": self.write_only_serializer,
                "_custom_field_definition_cache": self._custom_field_definition_cache,
            }
        )
        serializer = type(self)(instance=instance, data=data, **kwargs)
        serializer.filter = dict(self.filter)
        serializer.custom_field_type_input_field = self.custom_field_type_input_field
        serializer._unique_choice_field = self._unique_choice_field
        if self.parent is not None:
            serializer.bind(field_name=self.field_name, parent=self.parent)
        return serializer

    def _get_custom_field_type_config(
        self,
    ) -> tuple[str | None, serializers.Field | None, str | None, str | None]:
        type_attr = getattr(self.model, "_custom_field_type_attr", None)
        input_field = self.get_custom_field_type_input_field()
        static_fields = getattr(self, "_static_serializer_fields", None)
        if static_fields is None:
            self.fields
            static_fields = self._static_serializer_fields
        serializer_field = static_fields.get(input_field)
        if input_field and serializer_field is None and input_field != type_attr:
            raise ImproperlyConfigured(
                f"{type(self).__name__}.{input_field} must be declared in "
                "the serializer fields."
            )
        source = (
            serializer_field.source or input_field if serializer_field else input_field
        )
        if input_field and serializer_field is not None and type_attr:
            allowed_sources = {type_attr, f"{type_attr}_id"}
            if source not in allowed_sources:
                raise ImproperlyConfigured(
                    f"{type(self).__name__}.{input_field} must map to "
                    f"'{type_attr}' or '{type_attr}_id' through its source."
                )
        return input_field, serializer_field, source, type_attr

    def _preview_custom_field_type_value(
        self,
        input_field: str,
        serializer_field: serializers.Field,
        value: Any,
    ) -> Any:
        """Convert a type selector without running its validators.

        Dynamic fields must be known before DRF validates the complete payload. A
        bound copy provides the normal field context for conversion while leaving
        the real field untouched for the subsequent validation pass.
        """
        preview_field = copy.deepcopy(serializer_field)
        preview_field.bind(field_name=input_field, parent=self)
        is_empty, converted = preview_field.validate_empty_values(value)
        if not is_empty:
            converted = preview_field.to_internal_value(value)
        return converted

    @staticmethod
    def _normalize_custom_field_type_id(value: Any) -> int | None:
        if isinstance(value, models.Model):
            value = value.pk
        return int(value) if value is not None else None

    def _remember_custom_field_type_selection(
        self,
        *,
        input_field: str,
        source: str,
        type_id: int | None,
        must_be_present: bool,
        resolved: bool = True,
    ) -> int | None:
        self._custom_field_type_selection = CustomFieldTypeSelection(
            input_field=input_field,
            source=source,
            type_id=type_id,
            must_be_present=must_be_present,
            resolved=resolved,
        )
        self._custom_field_type_resolved = True
        self._resolved_custom_field_type_id = type_id
        return type_id

    def get_custom_field_type_id(self) -> int | None:
        if self._custom_field_type_resolved:
            return self._resolved_custom_field_type_id

        input_field, serializer_field, source, type_attr = (
            self._get_custom_field_type_config()
        )
        initial_data = getattr(self, "initial_data", empty)

        if (
            input_field
            and serializer_field is not None
            and not serializer_field.read_only
            and isinstance(initial_data, Mapping)
        ):
            submitted = input_field in initial_data
            value = initial_data[input_field] if submitted else empty
            try:
                converted = self._preview_custom_field_type_value(
                    input_field, serializer_field, value
                )
            except SkipField:
                pass
            except serializers.ValidationError:
                self._custom_field_type_resolution_failed = True
                return self._remember_custom_field_type_selection(
                    input_field=input_field,
                    source=source or input_field,
                    type_id=None,
                    must_be_present=submitted or serializer_field.required,
                    resolved=False,
                )
            else:
                try:
                    type_id = self._normalize_custom_field_type_id(converted)
                except (TypeError, ValueError):
                    self._custom_field_type_resolution_failed = True
                    return self._remember_custom_field_type_selection(
                        input_field=input_field,
                        source=source or input_field,
                        type_id=None,
                        must_be_present=True,
                        resolved=False,
                    )
                return self._remember_custom_field_type_selection(
                    input_field=input_field,
                    source=source or input_field,
                    type_id=type_id,
                    must_be_present=True,
                )

        type_id = None
        if isinstance(self.instance, self.model) and type_attr:
            type_id = getattr(self.instance, f"{type_attr}_id", None)
        if input_field and source:
            return self._remember_custom_field_type_selection(
                input_field=input_field,
                source=source,
                type_id=type_id,
                must_be_present=False,
            )
        self._custom_field_type_resolved = True
        self._resolved_custom_field_type_id = type_id
        return type_id

    def _get_validated_custom_field_type_id(
        self,
        selection: CustomFieldTypeSelection,
        validated_type: Any,
    ) -> int | None:
        type_attr = getattr(self.model, "_custom_field_type_attr", None)
        if not type_attr:
            return self._normalize_custom_field_type_id(validated_type)

        type_model = self.model._meta.get_field(type_attr).related_model
        if selection.source == type_attr:
            if validated_type is not None and not isinstance(
                validated_type, type_model
            ):
                raise ImproperlyConfigured(
                    f"{type(self).__name__}.{selection.input_field} maps to "
                    f"'{type_attr}' and must validate to a {type_model.__name__} "
                    "instance or None."
                )
        elif isinstance(validated_type, models.Model):
            raise ImproperlyConfigured(
                f"{type(self).__name__}.{selection.input_field} maps to "
                f"'{type_attr}_id' and must validate to a primary key or None, "
                "not a model instance."
            )

        try:
            type_id = self._normalize_custom_field_type_id(validated_type)
        except (TypeError, ValueError) as exc:
            raise ImproperlyConfigured(
                f"{type(self).__name__}.{selection.input_field} must validate to "
                "a numeric custom field type primary key."
            ) from exc

        if (
            selection.source == f"{type_attr}_id"
            and type_id is not None
            and not type_model._base_manager.filter(pk=type_id).exists()
        ):
            raise serializers.ValidationError(
                {
                    selection.input_field: [
                        _("The selected custom field type does not exist.")
                    ]
                }
            )
        return type_id

    def should_validate_custom_field_type_selection(
        self,
        selection: CustomFieldTypeSelection,
        validated_type: Any,
    ) -> bool:
        """Return whether a validated selector must match the selected type.

        Serializers that intentionally persist an intermediate relation value can
        opt out and take responsibility for resolving the type before they write
        type-specific custom fields.
        """
        return True

    def run_validation(self, data: Any = empty) -> Any:
        validated_data = super().run_validation(data)
        selection = self._custom_field_type_selection
        if selection is None:
            return validated_data

        validated_type = validated_data.get(selection.source, empty)
        if validated_type is empty and not selection.must_be_present:
            return validated_data
        if not self.should_validate_custom_field_type_selection(
            selection, validated_type
        ):
            return validated_data
        if validated_type is empty:
            validated_type_id = None
        else:
            validated_type_id = self._get_validated_custom_field_type_id(
                selection, validated_type
            )

        if (
            not selection.resolved
            or validated_type is empty
            or validated_type_id != selection.type_id
        ):
            raise serializers.ValidationError(
                {
                    selection.input_field: [
                        _(
                            "The validated type does not match the submitted "
                            "custom field type."
                        )
                    ]
                }
            )
        return validated_data

    def get_custom_fields_queryset(self) -> QuerySet:
        queryset = get_custom_field_model().objects.for_model(self.model)
        type_attr = getattr(self.model, "_custom_field_type_attr", None)
        if type_attr:
            type_model = self.model._meta.get_field(type_attr).related_model
            queryset = queryset.for_model_and_type(
                self.model, type_model, self.get_custom_field_type_id()
            )
        return queryset.filter(**self.filter)

    def is_custom_field_writable(self, custom_field: AbstractBaseCustomField) -> bool:
        return custom_field.editable

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if self.exclude_custom_fields or not isinstance(data, Mapping):
            return super().to_internal_value(data)

        # Evaluate the fields before applying custom-field policy so the applicable
        # field and identifier caches are populated.
        self.fields
        if self._custom_field_type_resolution_failed:
            return super().to_internal_value(data)
        applicable = {
            field.custom_field.identifier: field.custom_field
            for field in self._custom_fields
        }
        errors: dict[str, list[Any]] = {}
        for identifier in (self._all_custom_field_identifiers - set(applicable)) & set(
            data
        ):
            errors[identifier] = [
                _("This custom field does not belong to the selected type.")
            ]
        for identifier, custom_field in applicable.items():
            if identifier in data and not self.is_custom_field_writable(custom_field):
                errors[identifier] = [
                    _("This custom field may not be changed manually.")
                ]
        if errors:
            raise serializers.ValidationError(errors)
        return super().to_internal_value(data)

    def collect_custom_fields(self) -> dict:
        if not hasattr(self, "_custom_fields"):
            return {}

        if hasattr(self, "initial_data"):
            data = self.validated_data
        elif self.instance is not None:
            data = self.data
        else:
            return {}
        return {
            field.identifier: data.pop(field.identifier)
            for field in self._custom_fields
            if field.identifier in data
        }

    def create(self, validated_data: dict) -> Any:
        custom_value_instances: list[AbstractBaseCustomValue] = []
        choices: list[AbstractBaseCustomValue] = []
        representation_values: dict[str, Any] = {}
        for field in self._custom_fields:
            if field.identifier not in validated_data:
                continue
            value = validated_data.pop(field.identifier)
            representation_values[field.identifier] = value
            if value is None:
                continue
            if not field.choice_field:
                custom_value_instances.append(
                    get_custom_value_model()(
                        field_id=field.id,
                        value=self.fields[field.identifier].to_representation(value),
                    )
                )
            else:
                if field.multiple:
                    choices.extend(value)
                else:
                    choices.append(value)
        instance = super().create(validated_data)
        if custom_value_instances or choices:
            custom_values = get_custom_value_model().objects.bulk_create(
                custom_value_instances
            )
            custom_values.extend(choices)
            instance.custom_values.set(custom_values)
        self._set_custom_field_representation_values(
            instance,
            representation_values,
        )
        return instance

    @staticmethod
    def _set_custom_field_representation_values(
        instance: Any,
        values: dict[str, Any],
    ) -> None:
        """Keep the returned instance consistent with the values just persisted.

        Dynamic attributes are normally supplied by queryset annotations. Newly
        created instances do not have those annotations, and assigning through
        ``setattr`` could invoke the model's custom-value persistence hooks again.
        Updating ``__dict__`` provides representation state without another write
        or a per-instance refresh query.
        """
        instance.__dict__.update(values)

    def _create_or_update_custom_value(
        self, instance: CustomFieldBaseModel, field: CustomFieldData, value: Any
    ) -> None:
        serializer_field = field.serializer_field
        if value is not None:
            value = serializer_field.to_representation(value)
        try:
            value_object = instance.custom_values.select_related("field").get(
                field_id=field.id
            )
            if value is None:
                value_object.delete()
            else:
                value_object.value = value
                value_object.save()
        except get_custom_value_model().DoesNotExist:
            if value is not None:
                value_object = get_custom_value_model().objects.create(
                    field_id=field.id, value=value
                )
                instance.custom_values.add(value_object)

    def update(self, instance: Any, validated_data: dict) -> Any:
        representation_values: dict[str, Any] = {}
        for field in self._custom_fields:
            if field.identifier not in validated_data:
                continue
            value = validated_data.pop(field.identifier, None)
            representation_values[field.identifier] = value
            if field.choice_field:
                instance.custom_values.remove(*field.choices)
                if value is None:
                    continue
                if field.multiple:
                    instance.custom_values.add(*value)
                else:
                    instance.custom_values.add(value)
            else:
                self._create_or_update_custom_value(instance, field, value)
        instance = super().update(instance, validated_data)
        self._set_custom_field_representation_values(
            instance,
            representation_values,
        )
        return instance
