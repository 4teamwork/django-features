from typing import Any

from rest_framework import serializers

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
