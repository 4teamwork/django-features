from typing import Any

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.core.exceptions import ValidationError
from django.db.models import Model
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.related import RelatedField
from rest_framework.utils.model_meta import get_field_info

from django_features.custom_fields.models import CustomField


class MappingValidationMixin:
    _special_fields = ["unique_choice_field"]

    def __init__(
        self,
        allow_many_to_many: bool = True,
        allow_relations: bool = True,
        relation_separator: str = ".",
        validate_custom_fields: bool = True,
        validate_required: bool = True,
        validate_key: bool = False,
        validate_value: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.allow_many_to_many = allow_many_to_many
        self.allow_relations = allow_relations
        self.relation_separator = relation_separator
        self.validate_custom_fields = validate_custom_fields
        self.validate_required = validate_required
        self.validate_key = validate_key
        self.validate_value = validate_value
        super().__init__(*args, **kwargs)

    def validate_model(self, model_path: str) -> type[Model]:
        split_model = model_path.split(".")
        if len(split_model) == 1:
            content_types = ContentType.objects.filter(model=model_path)
        elif len(split_model) == 2:
            content_types = ContentType.objects.filter(
                app_label=split_model[0], model=split_model[1]
            )
        else:
            raise ValueError(f"Invalid model '{model_path}'.")

        if not content_types.exists():
            raise ValidationError(f"Model '{model_path}' does not exist.")
        if content_types.count() > 1:
            raise ValidationError(f"Multiple models found for '{model_path}'.")

        content_type = content_types.first()
        model_class = content_type.model_class()
        if not model_class:
            raise ValidationError(
                f"No model found for content type '{content_type}' with model {model_path}."
            )
        return model_class

    def valid_custom_fields(self, model: type[Model]) -> list:
        if not self.validate_custom_fields or not settings.CUSTOM_FIELDS_FEATURE:
            return []

        content_type = ContentType.objects.get_for_model(model)
        return list(
            CustomField.objects.filter(content_type=content_type)
            .values_list("identifier", flat=True)
            .distinct()
        )

    def validate_field(self, field_path: str, model: type[Model] | Any) -> None:
        split = field_path.split(self.relation_separator)
        field = split[0]

        if field in self.valid_custom_fields(model):
            return

        try:
            field = model._meta.get_field(field)
        except FieldDoesNotExist:
            raise ValidationError(f"Invalid field '{field}' for model {model}.")

        if field.is_relation and not self.allow_relations:
            raise ValidationError(
                f"Field '{field}' is a relation and cannot be assigned."
            )

        if field.many_to_many and not self.allow_many_to_many:
            raise ValidationError(
                f"Field '{field}' is a many-to-many relation and cannot be assigned."
            )

        if len(split) > 1 and isinstance(field, RelatedField):
            if field.many_to_many:
                raise ValidationError(
                    f"Field '{field}' is a many-to-many relation and cannot be nested."
                )
            if isinstance(field, GenericRelation):
                raise ValidationError(
                    f"Field '{field}' is a generic relation and cannot be nested."
                )
            self.validate_field(
                self.relation_separator.join(split[1:]), field.related_model
            )

    def validate_required_fields(
        self, model: type[Model], field_mapping: dict[str, Any]
    ) -> None:
        if not self.validate_required:
            return

        info = get_field_info(model)
        for name, field in info.fields.items():
            if (
                field.null is False
                and field.blank is False
                and field.default == NOT_PROVIDED
                and (
                    (name not in field_mapping.values() and self.validate_value)
                    or (name not in field_mapping.keys() and self.validate_key)
                )
                and (not hasattr(field, "auto_now_add") or field.auto_now_add is False)
                and (not hasattr(field, "auto_now") or field.auto_now is False)
            ):
                raise ValidationError(
                    f"Required field '{name}' not found in field mapping."
                )

    def validate_model_field_mapping(
        self, model: type[Model], field_mapping: dict[str, Any]
    ) -> None:
        if not isinstance(field_mapping, dict):
            raise ValidationError(
                "The value must be a dictionary with field names as keys and values."
            )
        self.validate_required_fields(model, field_mapping)
        for key, value in field_mapping.items():
            if self.validate_key:
                self.validate_field(key, model)
            if self.validate_value:
                self.validate_field(value, model)

    def validate_models_field_mapping(
        self, models_field_mapping: dict[str, Any]
    ) -> None:
        for model_path, field_mapping in models_field_mapping.items():
            if model_path in self._special_fields:
                continue
            model = self.validate_model(model_path)
            self.validate_model_field_mapping(model, field_mapping)
