from collections import namedtuple
from typing import Any

from django.db import models
from rest_framework import serializers
from rest_framework.fields import empty

from django_features.custom_fields.models import CustomField
from django_features.custom_fields.models import CustomFieldBaseModel
from django_features.custom_fields.models import CustomValue


class CustomChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomValue
        fields = ["id", "label", "value"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if isinstance(self.instance, CustomValue):
            field = self.instance.field
            self.fields["value"] = CustomField.TYPE_SERIALIZER_MAP[field.field_type](
                allow_null=True, read_only=True, required=False
            )


class CustomFieldSerializer(serializers.ModelSerializer):
    choices = serializers.SerializerMethodField()

    class Meta:
        model = CustomField
        fields = [
            "choice_field",
            "choices",
            "created",
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
        ]

    def get_choices(self, obj: CustomField) -> list:
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
    ],
)


class CustomFieldBaseModelSerializer(serializers.ModelSerializer):
    _custom_fields: list[CustomFieldData] = []
    _unique_choice_field = "id"
    _write_only_serializer = False

    class Meta:
        abstract = True
        fields = "__all__"
        model = None

    def __init__(
        self,
        instance: Any = None,
        data: Any = empty,
        exclude_custom_fields: bool = False,
        write_only_serializer: bool = False,
        **kwargs: Any,
    ) -> None:
        self.exclude_custom_fields: bool = exclude_custom_fields
        self.write_only_serializer = (
            write_only_serializer or self._write_only_serializer
        )
        super().__init__(instance, data, **kwargs)

    @property
    def model(self) -> models.Model:
        if not self.Meta.model:
            raise ValueError("Meta.model must be set")
        return self.Meta.model

    def get_fields(self) -> dict[str, Any]:
        fields = super().get_fields()
        if self.exclude_custom_fields:
            return fields
        self._custom_fields = []
        custom_fields = list(CustomField.objects.for_model(self.model))
        for field in custom_fields:
            self._custom_fields.append(
                CustomFieldData(
                    field.id,
                    field.identifier,
                    field.choices,
                    field.choice_field,
                    field.multiple,
                    field.serializer_field,
                )
            )
            serialized_field = field.serializer_field
            if field.choice_field:
                serialized_field.set_unique_field(self._unique_choice_field)
            fields[field.identifier] = serialized_field
        return fields

    def create(self, validated_data: dict) -> Any:
        custom_value_instances: list[CustomValue] = []
        choices: list[CustomValue] = []
        for field in self._custom_fields:
            value = validated_data.pop(field.identifier, None)
            if value is None:
                continue
            if not field.choice_field:
                custom_value_instances.append(
                    CustomValue(
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
            custom_values = CustomValue.objects.bulk_create(custom_value_instances)
            custom_values.extend(choices)
            instance.custom_values.set(custom_values)
        return instance

    def _create_or_update_custom_value(
        self, instance: CustomFieldBaseModel, field: CustomFieldData, value: Any
    ) -> None:
        serializer_field = field.serializer_field
        serializer_field.run_validators(value)
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
        except CustomValue.DoesNotExist:
            if value is not None:
                value_object = CustomValue.objects.create(
                    field_id=field.id, value=value
                )
                instance.custom_values.add(value_object)

    def update(self, instance: Any, validated_data: dict) -> Any:
        for field in self._custom_fields:
            if field.identifier not in validated_data:
                continue
            value = validated_data.pop(field.identifier, None)
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
        return instance
