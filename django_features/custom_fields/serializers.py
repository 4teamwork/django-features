from collections import namedtuple
from typing import Any

from django.db import models
from rest_framework import serializers
from rest_framework.fields import empty

from django_features.custom_fields.fields import ChoiceIdField
from django_features.custom_fields.models import CustomField
from django_features.custom_fields.models import CustomValue


class CustomChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomValue
        fields = ["id", "text", "value"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if isinstance(self.instance, CustomValue):
            field = self.instance.field
            self.fields["value"] = CustomField.TYPE_FIELD_MAP[field.field_type](
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
            "multiple_choice",
            "order",
        ]

    def get_choices(self, obj: CustomField) -> list:
        if not obj.choice_field:
            return []
        return CustomChoiceSerializer(
            CustomValue.objects.filter(field=obj), many=True
        ).data


CustomFieldData = namedtuple(
    "CustomFieldData",
    ["id", "identifier", "choice_field", "multiple_choice"],
)


class CustomFieldBaseModelSerializer(serializers.ModelSerializer):
    _custom_fields: list[CustomFieldData] = []

    class Meta:
        abstract = True
        fields = "__all__"
        model = None

    def __init__(
        self,
        instance: Any = None,
        data: Any = empty,
        exclude_custom_fields: bool = False,
        **kwargs: Any,
    ) -> None:
        self.exclude_custom_fields: bool = exclude_custom_fields
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
        custom_fields = list(CustomField.objects.for_model(self.model))
        for field in custom_fields:
            self._custom_fields.append(
                CustomFieldData(
                    field.id,
                    field.identifier,
                    field.choice_field,
                    field.multiple_choice,
                )
            )
            if field.choice_field:
                fields[f"{field.identifier}_id"] = ChoiceIdField(
                    required=field.required, write_only=True
                )
            fields[field.identifier] = field.serializer_field
        return fields

    def create(self, validated_data: dict) -> Any:
        custom_value_instances: list[CustomValue] = []
        choices: list[CustomValue] = []
        for field in self._custom_fields:
            if not field.choice_field:
                value = validated_data.pop(field.identifier, None)
                if not value:
                    continue
                custom_value_instances.append(
                    CustomValue(
                        field_id=field.id,
                        value=self.fields[field.identifier].to_representation(value),
                    )
                )
            else:
                value = validated_data.pop(f"{field.identifier}_id", None)
                if not value:
                    continue
                if field.multiple_choice:
                    choices.extend(value)
                else:
                    choices.append(value)
        instance = super().create(validated_data)
        if custom_value_instances or choices:
            custom_values = CustomValue.objects.bulk_create(custom_value_instances)
            custom_values.extend(choices)
            instance.custom_values.set(custom_values)
        return instance

    def update(self, instance: Any, validated_data: dict) -> Any:
        for field in self._custom_fields:
            value = validated_data.pop(field.identifier, None)
            if field.choice_field:
                value = validated_data.pop(f"{field.identifier}_id", None)
            if value is not None:
                setattr(instance, field.identifier, value)
        instance = super().update(instance, validated_data)
        return instance
