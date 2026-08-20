import copy
from collections.abc import Hashable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any
from typing import NamedTuple

from django.core.exceptions import FieldDoesNotExist
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.fields import SkipField

from django_features.custom_fields import helpers as custom_field_helpers
from django_features.custom_fields.helpers import get_custom_field_model
from django_features.custom_fields.helpers import get_custom_value_model
from django_features.custom_fields.models.base import CustomFieldBaseModel
from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.field import CustomFieldQuerySet
from django_features.custom_fields.models.value import AbstractBaseCustomValue
from django_features.custom_fields.models.value import CustomValueQuerySet


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


class CustomFieldData(NamedTuple):
    id: int
    identifier: str
    choices: CustomValueQuerySet
    choice_field: bool
    multiple: bool
    serializer_field: serializers.Field
    custom_field: AbstractBaseCustomField


@dataclass
class CustomFieldDefinitionCache:
    fields_by_type: dict[Hashable, list[AbstractBaseCustomField]] = dataclass_field(
        default_factory=dict
    )
    identifiers_by_filter: dict[Hashable, set[str]] = dataclass_field(
        default_factory=dict
    )
    identifiers_by_model: dict[type[models.Model], set[str]] = dataclass_field(
        default_factory=dict
    )


@dataclass(frozen=True)
class CustomFieldTypeSelection:
    input_field: str
    source: str
    type_id: int | None
    must_be_present: bool
    resolved: bool = True


@dataclass(frozen=True)
class CustomFieldTypeConfig:
    input_field: str
    serializer_field: serializers.Field | None
    source: str


@dataclass(frozen=True)
class CustomFieldTypeResolution:
    type_id: int | None
    selection: CustomFieldTypeSelection | None = None

    @property
    def failed(self) -> bool:
        return self.selection is not None and not self.selection.resolved


class _UnresolvedCustomFieldType:
    pass


UNRESOLVED_CUSTOM_FIELD_TYPE = _UnresolvedCustomFieldType()


class _NoValidatedListData:
    pass


NO_VALIDATED_LIST_DATA = _NoValidatedListData()


class CustomFieldListSerializer(serializers.ListSerializer):
    """Use a dedicated child serializer for every list item.

    Dynamic custom fields depend on an item's configured type. DRF normally reuses
    one child serializer for an entire list, which cannot represent or validate a
    heterogeneous list correctly.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._custom_field_definition_cache = CustomFieldDefinitionCache()
        self.child._custom_field_definition_cache = self._custom_field_definition_cache
        self._validated_item_serializers: list[CustomFieldBaseModelSerializer] = []
        self._validated_item_values: tuple[Any, ...] = ()
        self._paired_item_serializers: list[CustomFieldBaseModelSerializer] = []
        self._paired_item_values: tuple[Any, ...] = ()
        self._validated_list_data: list[Any] | _NoValidatedListData = (
            NO_VALIDATED_LIST_DATA
        )

    def to_internal_value(self, data: Any) -> list[Any]:
        self._validated_item_serializers = []
        self._validated_item_values = ()
        self._paired_item_serializers = []
        self._paired_item_values = ()
        self._validated_list_data = NO_VALIDATED_LIST_DATA
        values = super().to_internal_value(data)
        self._validated_item_values = tuple(values)
        return values

    def run_child_validation(self, data: Any) -> Any:
        serializer = self.child.for_item(data=data)
        self._validated_item_serializers.append(serializer)
        return serializer.run_validation(data)

    def get_paired_item_serializers(
        self,
        validated_data: list[Any],
    ) -> list["CustomFieldBaseModelSerializer"]:
        """Pair validated items with their type-specific serializers.

        The default contract allows a list validator to return a new list, but it
        must preserve every validated item in its original position. Serializers
        that intentionally replace, reorder, add, or remove items can override this
        hook and return the matching serializer for every resulting item.
        """
        if len(self._validated_item_serializers) != len(validated_data):
            raise AssertionError(
                "List validation changed the number of custom-field serializer "
                "items. Override get_paired_item_serializers() to define how they "
                "should be matched."
            )
        if len(self._validated_item_values) != len(validated_data) or any(
            before is not after
            for before, after in zip(
                self._validated_item_values,
                validated_data,
                strict=True,
            )
        ):
            raise AssertionError(
                "List validation replaced or reordered custom-field serializer "
                "items. Override get_paired_item_serializers() to define how they "
                "should be matched."
            )
        return list(self._validated_item_serializers)

    def run_validation(self, data: Any = empty) -> Any:
        validated_data = super().run_validation(data)
        paired_item_serializers = self.get_paired_item_serializers(validated_data)
        if len(paired_item_serializers) != len(validated_data):
            raise AssertionError(
                "get_paired_item_serializers() must return one custom-field "
                "serializer for every validated list item."
            )
        self._validate_paired_type_selections(
            paired_item_serializers,
            validated_data,
        )
        self._paired_item_serializers = paired_item_serializers
        self._paired_item_values = tuple(validated_data)
        self._validated_list_data = validated_data
        return validated_data

    @staticmethod
    def _validate_paired_type_selections(
        item_serializers: list["CustomFieldBaseModelSerializer"],
        data: list[Any],
    ) -> None:
        for index, (serializer, item) in enumerate(
            zip(item_serializers, data, strict=True)
        ):
            try:
                serializer._validate_custom_field_type_selection(
                    item,
                    validate_existence=False,
                )
            except (ImproperlyConfigured, serializers.ValidationError) as exc:
                raise AssertionError(
                    "List data changed the custom-field type selected for item "
                    f"{index}. Override get_paired_item_serializers() and the "
                    "type-selection policy to support that transformation."
                ) from exc

    def _paired_serializers_for(
        self,
        data: list[Any],
        *,
        require_identity: bool,
    ) -> list["CustomFieldBaseModelSerializer"]:
        if len(self._paired_item_serializers) != len(data):
            raise AssertionError(
                "Validated list data no longer matches its custom-field serializer "
                "items. Override create() or to_representation() to define how "
                "they should be matched."
            )
        if require_identity and (
            len(self._paired_item_values) != len(data)
            or any(
                paired is not current
                for paired, current in zip(
                    self._paired_item_values,
                    data,
                    strict=True,
                )
            )
        ):
            raise AssertionError(
                "Validated list items were replaced or reordered after custom-field "
                "serializer pairing."
            )
        self._validate_paired_type_selections(self._paired_item_serializers, data)
        return self._paired_item_serializers

    def create(self, validated_data: list[dict[str, Any]]) -> list[Any]:
        return [
            serializer.create(attrs)
            for serializer, attrs in zip(
                self._paired_serializers_for(
                    validated_data,
                    require_identity=False,
                ),
                validated_data,
                strict=True,
            )
        ]

    def save(self, **kwargs: Any) -> list[Any]:
        # Check the original validated objects before DRF copies every item and
        # merges ``save()`` keyword arguments in ListSerializer.save().
        item_serializers = self._paired_serializers_for(
            self.validated_data,
            require_identity=True,
        )
        merged_data = [{**attrs, **kwargs} for attrs in self.validated_data]
        self._validate_paired_type_selections(item_serializers, merged_data)
        return super().save(**kwargs)

    def to_representation(self, data: Any) -> list[Any]:
        if data is self._validated_list_data:
            return [
                serializer.to_representation(item)
                for serializer, item in zip(
                    self._paired_serializers_for(data, require_identity=True),
                    data,
                    strict=True,
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
        self._custom_field_type_resolution: (
            CustomFieldTypeResolution | _UnresolvedCustomFieldType
        ) = UNRESOLVED_CUSTOM_FIELD_TYPE
        self._static_serializer_fields: dict[str, serializers.Field] | None = None
        self._custom_fields = []
        self._all_custom_field_identifiers: set[str] = set()
        self._all_custom_field_identifiers_resolved = False
        self._model_custom_field_identifiers: set[str] = set()
        self._model_custom_field_identifiers_resolved = False
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
        if self.custom_field_type_input_field is None and self.Meta.model is not None:
            self.custom_field_type_input_field = getattr(
                self.Meta.model,
                "_custom_field_type_attr",
                None,
            )
        super().__init__(instance, data, **kwargs)

    @classmethod
    def get_list_serializer_kwargs(
        cls,
        child: "CustomFieldBaseModelSerializer",
    ) -> dict[str, Any]:
        """Return extra arguments for the serializer used by ``many=True``."""
        return {}

    @classmethod
    def many_init(cls, *args: Any, **kwargs: Any) -> serializers.ListSerializer:
        """Use the custom list serializer unless a subclass explicitly replaces it."""
        list_kwargs: dict[str, Any] = {}
        for key in serializers.LIST_SERIALIZER_KWARGS_REMOVE:
            value = kwargs.pop(key, None)
            if value is not None:
                list_kwargs[key] = value
        child = cls(*args, **kwargs)
        list_kwargs["child"] = child
        list_kwargs.update(cls.get_list_serializer_kwargs(child))
        list_kwargs.update(
            {
                key: value
                for key, value in kwargs.items()
                if key in serializers.LIST_SERIALIZER_KWARGS
            }
        )
        meta = getattr(cls, "Meta", None)
        list_serializer_class = getattr(
            meta,
            "list_serializer_class",
            getattr(cls, "list_serializer_class", CustomFieldListSerializer),
        )
        return list_serializer_class(*args, **list_kwargs)

    @property
    def model(self) -> type[models.Model]:
        model = getattr(self, "_model", self.Meta.model)
        if not model:
            raise ValueError("Meta.model must be set")
        return model

    @model.setter
    def model(self, value: type[models.Model]) -> None:
        self._model = value

    @property
    def filter(self) -> dict[str, Any]:
        return self._filter

    @filter.setter
    def filter(self, value: dict[str, Any]) -> None:
        self._filter = value
        self._all_custom_field_identifiers = set()
        self._all_custom_field_identifiers_resolved = False

    @property
    def custom_field_type_attr(self) -> str | None:
        return getattr(self.model, "_custom_field_type_attr", None)

    @property
    def custom_field_type_model(self) -> type[models.Model] | None:
        type_attr = self.custom_field_type_attr
        if not type_attr:
            return None
        try:
            model_field = self.model._meta.get_field(type_attr)
        except FieldDoesNotExist as exc:
            raise ImproperlyConfigured(
                f"{self.model.__name__}._custom_field_type_attr refers to unknown "
                f"field '{type_attr}'."
            ) from exc
        type_model = model_field.related_model
        if type_model is None:
            raise ImproperlyConfigured(
                f"{self.model.__name__}._custom_field_type_attr must refer to a "
                f"related model field; '{type_attr}' is not relational."
            )
        return type_model

    def _get_static_fields(self) -> dict[str, serializers.Field]:
        if self._static_serializer_fields is None:
            self._static_serializer_fields = super().get_fields()
        return self._static_serializer_fields

    def _ensure_fields_initialized(self) -> dict[str, serializers.Field]:
        return self.fields

    @property
    def _filter_cache_key(self) -> Hashable:
        return tuple(sorted((key, repr(value)) for key, value in self.filter.items()))

    def get_model_custom_field_identifiers(self) -> set[str]:
        """Return every custom-field identifier configured for this model."""
        if self._model_custom_field_identifiers_resolved:
            return self._model_custom_field_identifiers

        cache = self._custom_field_definition_cache
        if cache is not None and self.model in cache.identifiers_by_model:
            identifiers = cache.identifiers_by_model[self.model]
        else:
            identifiers = set(
                get_custom_field_model()
                .objects.for_model(self.model)
                .values_list("identifier", flat=True)
            )
            if cache is not None:
                cache.identifiers_by_model[self.model] = identifiers

        self._model_custom_field_identifiers = identifiers
        self._model_custom_field_identifiers_resolved = True
        return identifiers

    def validate_custom_field_identifiers(
        self,
        static_fields: Mapping[str, serializers.Field],
    ) -> None:
        serializer_reserved = set(static_fields)
        for serializer_field in static_fields.values():
            source = serializer_field.source
            if not serializer_field.read_only and source not in (None, "*"):
                serializer_reserved.add(source.split(".", 1)[0])
        custom_field_helpers.validate_custom_field_identifiers(
            self.model,
            self.get_model_custom_field_identifiers(),
            extra_reserved=serializer_reserved,
        )

    def get_fields(self) -> dict[str, Any]:
        fields = dict(self._get_static_fields())
        self.validate_custom_field_identifiers(fields)
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
                if field.choice_field:
                    serialized_field.set_unique_field(self._unique_choice_field)
            except ValueError as exc:
                raise ImproperlyConfigured(
                    f"Cannot build custom field '{field.identifier}' for "
                    f"{self.model._meta.label}: {exc}"
                ) from exc
            if not self.is_custom_field_writable(field):
                # Server-managed fields are never required client input. Keep
                # their configured default for creates even when the custom-field
                # definition itself is marked as required.
                serialized_field.required = False
                if field.default is not None:
                    serialized_field.default = field.validated_serializer_default
            if isinstance(self.instance, self.model):
                # Custom-field defaults are create-only. Both full and partial
                # updates preserve every omitted custom value.
                serialized_field.default = empty
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

        if not self.filter:
            identifiers = self.get_model_custom_field_identifiers()
            self._all_custom_field_identifiers = identifiers
            self._all_custom_field_identifiers_resolved = True
            return identifiers

        filter_key = self._filter_cache_key
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

    def get_custom_fields_cache_key(self) -> Hashable:
        """Return the per-list cache key for the applicable custom fields."""
        return self.get_custom_field_type_id(), self._filter_cache_key

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
    ) -> CustomFieldTypeConfig | None:
        input_field = self.get_custom_field_type_input_field()
        if not input_field:
            return None

        type_attr = self.custom_field_type_attr
        static_fields = self._get_static_fields()
        serializer_field = static_fields.get(input_field)
        if serializer_field is None and input_field != type_attr:
            raise ImproperlyConfigured(
                f"{type(self).__name__}.{input_field} must be declared in "
                "the serializer fields."
            )
        source = (
            serializer_field.source or input_field if serializer_field else input_field
        )
        if serializer_field is not None and type_attr:
            allowed_sources = {type_attr, f"{type_attr}_id"}
            if source not in allowed_sources:
                raise ImproperlyConfigured(
                    f"{type(self).__name__}.{input_field} must map to "
                    f"'{type_attr}' or '{type_attr}_id' through its source."
                )
        return CustomFieldTypeConfig(
            input_field=input_field,
            serializer_field=serializer_field,
            source=source,
        )

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

    def _resolution_with_selection(
        self,
        *,
        config: CustomFieldTypeConfig,
        type_id: int | None,
        must_be_present: bool,
        resolved: bool = True,
    ) -> CustomFieldTypeResolution:
        selection = CustomFieldTypeSelection(
            input_field=config.input_field,
            source=config.source,
            type_id=type_id,
            must_be_present=must_be_present,
            resolved=resolved,
        )
        return CustomFieldTypeResolution(type_id=type_id, selection=selection)

    def _type_resolution_from_input(
        self,
        config: CustomFieldTypeConfig,
    ) -> CustomFieldTypeResolution | None:
        serializer_field = config.serializer_field
        initial_data = getattr(self, "initial_data", empty)
        if (
            serializer_field is None
            or serializer_field.read_only
            or not isinstance(initial_data, Mapping)
        ):
            return None

        submitted = config.input_field in initial_data
        value = initial_data[config.input_field] if submitted else empty
        try:
            converted = self._preview_custom_field_type_value(
                config.input_field,
                serializer_field,
                value,
            )
        except SkipField:
            return None
        except serializers.ValidationError:
            return self._resolution_with_selection(
                config=config,
                type_id=None,
                must_be_present=submitted or serializer_field.required,
                resolved=False,
            )

        try:
            type_id = self._normalize_custom_field_type_id(converted)
        except (TypeError, ValueError):
            return self._resolution_with_selection(
                config=config,
                type_id=None,
                must_be_present=True,
                resolved=False,
            )
        return self._resolution_with_selection(
            config=config,
            type_id=type_id,
            must_be_present=True,
        )

    def _type_resolution_from_instance(
        self,
        config: CustomFieldTypeConfig | None,
    ) -> CustomFieldTypeResolution:
        type_id = None
        type_attr = self.custom_field_type_attr
        if isinstance(self.instance, self.model) and type_attr:
            type_id = getattr(self.instance, f"{type_attr}_id", None)
        if config is None:
            return CustomFieldTypeResolution(type_id=type_id)
        return self._resolution_with_selection(
            config=config,
            type_id=type_id,
            must_be_present=False,
        )

    def get_custom_field_type_id(self) -> int | None:
        cached_resolution = self._custom_field_type_resolution
        if isinstance(cached_resolution, CustomFieldTypeResolution):
            return cached_resolution.type_id

        config = self._get_custom_field_type_config()
        input_resolution = (
            self._type_resolution_from_input(config) if config is not None else None
        )
        resolution = input_resolution or self._type_resolution_from_instance(config)
        self._custom_field_type_resolution = resolution
        return resolution.type_id

    def _get_validated_custom_field_type_id(
        self,
        selection: CustomFieldTypeSelection,
        validated_type: Any,
        *,
        source: str | None = None,
        validate_existence: bool = True,
    ) -> int | None:
        type_attr = self.custom_field_type_attr
        if not type_attr:
            return self._normalize_custom_field_type_id(validated_type)

        source = source or selection.source
        type_model = self.custom_field_type_model
        if type_model is None:
            raise AssertionError("A configured custom-field type must have a model.")
        if source == type_attr:
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
            validate_existence
            and source == f"{type_attr}_id"
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

    @staticmethod
    def _custom_field_type_mismatch_error(
        selection: CustomFieldTypeSelection,
    ) -> serializers.ValidationError:
        return serializers.ValidationError(
            {
                selection.input_field: [
                    _(
                        "The validated type does not match the submitted "
                        "custom field type."
                    )
                ]
            }
        )

    def _validate_custom_field_type_selection(
        self,
        validated_data: Mapping[str, Any],
        *,
        validate_existence: bool = True,
    ) -> None:
        resolution = self._custom_field_type_resolution
        if not isinstance(resolution, CustomFieldTypeResolution):
            return
        selection = resolution.selection
        if selection is None:
            return

        validated_type = validated_data.get(selection.source, empty)
        type_attr = self.custom_field_type_attr
        alternate_sources = []
        if type_attr:
            alternate_sources = [
                source
                for source in (type_attr, f"{type_attr}_id")
                if source != selection.source and source in validated_data
            ]

        if (
            validated_type is empty
            and not selection.must_be_present
            and not alternate_sources
        ):
            return
        policy_value = (
            validated_type
            if validated_type is not empty
            else (validated_data[alternate_sources[0]] if alternate_sources else empty)
        )
        if not self.should_validate_custom_field_type_selection(
            selection,
            policy_value,
        ):
            return
        if validated_type is empty:
            if selection.must_be_present or not selection.resolved:
                raise self._custom_field_type_mismatch_error(selection)
        else:
            validated_type_id = self._get_validated_custom_field_type_id(
                selection,
                validated_type,
                validate_existence=validate_existence,
            )
            if not selection.resolved or validated_type_id != selection.type_id:
                raise self._custom_field_type_mismatch_error(selection)

        for alternate_source in alternate_sources:
            alternate_id = self._get_validated_custom_field_type_id(
                selection,
                validated_data[alternate_source],
                source=alternate_source,
                validate_existence=validate_existence,
            )
            if validated_type is not empty or alternate_id != selection.type_id:
                raise self._custom_field_type_mismatch_error(selection)

    def run_validation(self, data: Any = empty) -> Any:
        validated_data = super().run_validation(data)
        self._validate_custom_field_type_selection(validated_data)
        return validated_data

    def get_custom_fields_queryset(self) -> CustomFieldQuerySet:
        queryset = get_custom_field_model().objects.for_model(self.model)
        if self.custom_field_type_attr:
            type_model = self.custom_field_type_model
            if type_model is None:
                raise AssertionError(
                    "A configured custom-field type must have a model."
                )
            queryset = queryset.for_model_and_type(
                self.model, type_model, self.get_custom_field_type_id()
            )
        return queryset.filter(**self.filter)

    def is_custom_field_writable(self, custom_field: AbstractBaseCustomField) -> bool:
        return custom_field.editable

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if self.exclude_custom_fields or not isinstance(data, Mapping):
            return super().to_internal_value(data)

        # Initialize dynamic fields before applying custom-field policy so the
        # applicable field and identifier caches are populated.
        self._ensure_fields_initialized()
        resolution = self._custom_field_type_resolution
        if isinstance(resolution, CustomFieldTypeResolution) and resolution.failed:
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
        self._validate_custom_field_type_selection(
            validated_data,
            validate_existence=False,
        )
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
        self._validate_custom_field_type_selection(
            validated_data,
            validate_existence=False,
        )
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
