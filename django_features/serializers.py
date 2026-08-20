from typing import Any

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import FieldDoesNotExist
from django.core.exceptions import ValidationError
from django.db import models
from rest_framework.fields import empty
from rest_framework.relations import ManyRelatedField

from django_features.custom_fields.serializers import CustomFieldBaseModelSerializer
from django_features.custom_fields.serializers import CustomFieldListSerializer
from django_features.custom_fields.serializers import CustomFieldTypeSelection
from django_features.fields import UUIDRelatedField


class PropertySerializerMixin:
    relation_separator: str = "."

    class Meta:
        abstract = True
        fields = "__all__"
        model = None

    @property
    def mapping(self) -> dict[str, dict[str, Any]]:
        if getattr(self, "_mapping") is None:
            raise ValueError(
                "Property 'mapping' on instance must be set and can't be 'None'"
            )
        return self._mapping

    @mapping.setter
    def mapping(self, value: dict[str, dict[str, Any]]) -> None:
        self._mapping = value

    @property
    def mapping_fields(self) -> list[str]:
        mapping_fields = getattr(
            self, "_mapping_fields", list(self.model_mapping.values())
        )
        if mapping_fields is None:
            raise ValueError("Property 'mapping_fields' must be set and can't be 'None")
        return mapping_fields

    @mapping_fields.setter
    def mapping_fields(self, value: list[str]) -> None:
        self._mapping_fields = value

    @property
    def model_mapping(self) -> dict[str, Any]:
        for key_path in self.mapping.keys():
            key = key_path.split(self.relation_separator)[-1]
            if key.lower() == self.model.__name__.lower():
                return self.mapping.get(key_path, {})
        return {}

    @model_mapping.setter
    def model_mapping(self, value: dict[str, Any]) -> None:
        self._model_mapping = value

    @property
    def model(self) -> type[models.Model]:
        model = getattr(self, "_model", self.Meta.model)
        if model is None:
            raise ValueError(
                "Property 'model' must be set and can't be 'None. Default is 'Meta.model"
            )
        return model

    @model.setter
    def model(self, value: type[models.Model]) -> None:
        self._model = value


class BaseMappingSerializer(CustomFieldBaseModelSerializer, PropertySerializerMixin):
    serializer_related_field = UUIDRelatedField
    serializer_related_fields: dict[str, Any] = {}

    _write_only_serializer = True

    class Meta:
        abstract = True
        fields = "__all__"
        model = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._unique_choice_field = str(
            self.mapping.get("unique_choice_field", "value")
        )
        super().__init__(*args, **kwargs)
        self.exclude: list[str] = []
        self.related_fields: set[str] = set()

    def get_fields(self) -> dict[str, Any]:
        initial_fields = super().get_fields()
        fields: dict[str, Any] = dict()
        nested_fields: dict[str, Any] = dict()
        nested_field_fields: dict[str, list[str]] = dict()
        for internal_name in self.mapping_fields:
            if internal_name in self.exclude:
                continue
            split = internal_name.split(self.relation_separator)
            field_name = split[0]
            serializer_field = initial_fields.get(field_name)
            if serializer_field is not None and (
                field_name in self._declared_fields or len(split) == 1
            ):
                fields[field_name] = serializer_field
            else:
                try:
                    field = self.model._meta.get_field(field_name)
                except FieldDoesNotExist:
                    if self.is_known_custom_field_identifier(field_name):
                        # The mapping may contain custom fields for several model
                        # types. Per-item policy below rejects submitted values for
                        # the wrong type; fields absent from this item's type are
                        # not invalid model configuration.
                        continue
                    raise ValidationError(
                        f"Invalid field '{field_name}' for model {self.model}."
                    )
                if len(split) > 1:
                    nested_field = self.relation_separator.join(split[1:])
                    if field_name not in nested_fields:
                        nested_fields[field_name] = field
                    if field_name in nested_field_fields:
                        nested_field_fields[field_name].append(nested_field)
                    else:
                        nested_field_fields[field_name] = [nested_field]
                elif isinstance(field, GenericRelation):
                    self.related_fields.add(field_name)
                    serializer_related_field = self.serializer_related_fields.get(
                        internal_name, self.serializer_related_field
                    )
                    fields[internal_name] = ManyRelatedField(
                        child_relation=serializer_related_field(
                            field=field, required=False
                        ),
                        required=False,
                    )
        initial_data = getattr(self, "initial_data", {})
        if not isinstance(initial_data, dict):
            initial_data = {}
        for field_name, field in nested_fields.items():
            nested_data = initial_data.get(field_name, empty)
            if not isinstance(nested_data, dict):
                nested_data = empty
            self.related_fields.add(field_name)
            fields[field_name] = NestedMappingSerializer(
                data=nested_data,
                exclude=[*self.exclude, self.model.__name__.lower()],
                exclude_custom_fields=self.exclude_custom_fields,
                field=field,
                nested_fields=nested_field_fields[field_name],
                parent_mapping=self.mapping,
                required=False,
            )
        missing_declared_fields = self._declared_fields.keys() - fields.keys()
        fields.update(
            {field: initial_fields[field] for field in missing_declared_fields}
        )
        self.fields = fields
        return fields

    def should_map_internal_field(self, internal_name: str) -> bool:
        if not self.exclude_custom_fields:
            return True

        field_name = internal_name.split(self.relation_separator, 1)[0]
        return field_name not in self.get_model_custom_field_identifiers()

    def should_validate_custom_field_type_selection(
        self,
        selection: CustomFieldTypeSelection,
        validated_type: Any,
    ) -> bool:
        serializer_field = self.fields.get(selection.input_field)
        return not isinstance(serializer_field, NestedMappingSerializer)

    def create(self, validated_data: dict[str, Any]) -> models.Model:
        self._validate_custom_field_type_selection(
            validated_data,
            validate_existence=False,
        )
        relations_to_save: dict[str, Any] = {}
        for field in self.related_fields:
            if field not in validated_data:
                continue
            value = validated_data.pop(field)
            serializer = self.fields.get(field)
            if isinstance(serializer, NestedMappingSerializer):
                relations_to_save[field] = serializer.create(value)
            elif value is not None:
                relations_to_save[field] = value
        instance = super().create(validated_data)
        for field, value in relations_to_save.items():
            model_field = self.model._meta.get_field(field)
            if model_field.many_to_many or model_field.one_to_many:
                getattr(instance, field).set(value)
            if model_field.one_to_one or model_field.many_to_one:
                setattr(instance, field, value)
        instance.save()
        return instance

    def update(
        self, instance: models.Model, validated_data: dict[str, Any]
    ) -> models.Model:
        self._validate_custom_field_type_selection(
            validated_data,
            validate_existence=False,
        )
        for field in self.related_fields:
            if field not in validated_data:
                continue
            value = validated_data.pop(field)
            serializer = self.fields.get(field)
            if isinstance(serializer, NestedMappingSerializer):
                value = serializer.create(value)
            model_field = self.model._meta.get_field(field)
            if model_field.many_to_many or model_field.one_to_many:
                getattr(instance, field).set(value)
            if model_field.one_to_one or model_field.many_to_one:
                setattr(instance, field, value)
        return super().update(instance, validated_data)


class NestedMappingSerializer(BaseMappingSerializer):
    class Meta:
        fields = "__all__"
        model = None

    def __init__(
        self,
        exclude: list,
        field: models.Field,
        nested_fields: list,
        parent_mapping: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.exclude = exclude
        self.mapping_fields = nested_fields
        self.mapping = parent_mapping

        class Meta(self.Meta):  # type: ignore[name-defined]
            model = field.related_model

        self.Meta = Meta  # type: ignore[misc]
        super().__init__(*args, **kwargs)


class DataMappingSerializerMixin(PropertySerializerMixin):
    _default_prefix = "default"
    _format_prefix = "format"
    unmapped_data: Any = empty

    def should_map_internal_field(self, internal_name: str) -> bool:
        return True

    def _get_nested_data(self, field_path: list[str], data: Any) -> tuple[Any, bool]:
        field_name = field_path[0]
        if not isinstance(data, dict) or field_name not in data:
            return None, False
        value = data[field_name]
        if len(field_path) > 1:
            return self._get_nested_data(field_path[1:], value)
        return value, True

    def _get_data_with_internal_key(
        self, field_path: list[str], parent_data: dict[str, Any] | Any, value: Any
    ) -> dict[str, Any] | Any:
        field_name = field_path[0]
        if len(field_path) > 1:
            nested_data = parent_data.get(field_name, {})
            value = self._get_data_with_internal_key(field_path[1:], nested_data, value)
            if field_name in parent_data:
                nested_data.update(value)
                parent_data.update({field_name: nested_data})
                return parent_data
        return {field_name: value}

    def map_data(self, initial_data: Any) -> Any:
        if not isinstance(initial_data, dict):
            return initial_data

        previous_unmapped_data = getattr(self, "unmapped_data", empty)
        self.unmapped_data = initial_data
        try:
            data: dict[str, Any] = {}
            for external_name, internal_name in self.model_mapping.items():
                if not self.should_map_internal_field(internal_name):
                    continue
                external_field_path = external_name.split(self.relation_separator)
                value, found = self._get_nested_data(external_field_path, initial_data)
                if not found:
                    default_func = getattr(
                        self, f"{self._default_prefix}_{internal_name}", None
                    )
                    if default_func is not None:
                        value = default_func()
                    else:
                        continue
                format_func = getattr(
                    self, f"{self._format_prefix}_{internal_name}", None
                )
                if format_func is not None:
                    value = format_func(value)
                internal_field_path = internal_name.split(self.relation_separator)
                data.update(
                    self._get_data_with_internal_key(internal_field_path, data, value)
                )
            return data
        finally:
            self.unmapped_data = previous_unmapped_data


class ListDataMappingSerializer(
    DataMappingSerializerMixin,
    CustomFieldListSerializer,
):
    def __init__(
        self,
        instance: Any = None,
        data: Any = empty,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.mapping = kwargs.pop("mapping", {})
        self.model = kwargs.pop("model")
        self.unmapped_data = data if data is not empty else []
        super().__init__(instance, data, *args, **kwargs)
        if data is not empty:
            self.initial_data = self.map_list_data(data)

    def map_data(self, initial_data: Any) -> Any:
        return self.child.map_data(initial_data)

    def map_list_data(self, initial_data: Any) -> Any:
        if not isinstance(initial_data, list):
            return initial_data
        return [self.map_data(item) for item in initial_data]

    def run_child_validation(self, data: Any) -> Any:
        index = len(self._validated_item_serializers)
        unmapped_data = empty
        if isinstance(self.unmapped_data, list) and index < len(self.unmapped_data):
            unmapped_data = self.unmapped_data[index]
        serializer = self.child.for_mapped_item(
            data=data,
            unmapped_data=unmapped_data,
        )
        self._validated_item_serializers.append(serializer)
        return serializer.run_validation(data)


class MappingSerializer(BaseMappingSerializer, DataMappingSerializerMixin):
    list_serializer_class = ListDataMappingSerializer

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
        self.unmapped_data = data
        super().__init__(instance=instance, data=empty, **kwargs)
        if data is not empty:
            self.initial_data = self.map_data(data)

    def for_mapped_item(
        self,
        *,
        data: Any,
        unmapped_data: Any,
    ) -> "MappingSerializer":
        """Build one item serializer without applying the list mapping twice."""
        serializer = self.for_item(data=empty)
        serializer.initial_data = data
        serializer.unmapped_data = unmapped_data
        return serializer

    @classmethod
    def get_list_serializer_kwargs(
        cls,
        child: CustomFieldBaseModelSerializer,
    ) -> dict[str, Any]:
        list_kwargs = super().get_list_serializer_kwargs(child)
        list_kwargs.update(
            {
                "mapping": getattr(child, "mapping", {}),
                "model": child.model,
            }
        )
        return list_kwargs
