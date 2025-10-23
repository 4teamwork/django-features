from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class RelatedField(serializers.RelatedField):
    """
    A relation field which expects an uid to be present on the related model for lookup and representation.
    """

    default_related_field_name = "id"

    default_error_messages = {
        "does_not_exist": _("Objekt existiert nicht."),
        "incorrect_type": _("Inkorrekter Typ."),
    }

    def __init__(
        self,
        field: models.Field | None = None,
        queryset: QuerySet | None = None,
        related_field_name: str | None = None,
        creation: bool = True,
        **kwargs: Any,
    ) -> None:
        self.creation = creation
        self.field = field
        self.queryset = queryset
        self.related_field_name = related_field_name or self.default_related_field_name
        super().__init__(**kwargs)

    def get_field(self) -> models.Field:
        if self.field:
            field = self.field
        elif self.queryset:
            field = self.queryset.model._meta.get_field(self.field_name)
        elif self.parent.Meta and self.parent.Meta.model:
            field = self.parent.Meta.model._meta.get_field(self.field_name)
        else:
            raise ValidationError(
                f"No field or queryset defined for field {self.field_name} "
                f"and parent class {self.parent.__class__} has no attribute Meta."
            )
        if not field.is_relation:
            raise ValidationError(f"Field {self.field_name} is not a relation field.")
        return field

    def get_queryset(self) -> QuerySet:
        return self.queryset or self.get_field().related_model.objects

    def to_representation(self, related_obj: models.Model) -> None | str:
        """
        Get the related value of the object; format it as UID.
        """
        if not related_obj:
            return None
        related_field = getattr(related_obj, self.related_field_name, None)
        if related_field is None and not self.required:
            raise AttributeError(
                f"No field named 'UID' defined for relation to {self.field_name} on {related_obj}"
            )
        return related_field

    def to_internal_value(self, data: str) -> models.Model | None:
        """
        Assume that the model is defined on the serializer using this field.
        """
        if not data and not self.required:
            return None
        try:
            return self.get_queryset().get(**{self.related_field_name: data})
        except ObjectDoesNotExist as e:
            if self.required:
                raise ValidationError(
                    f"Object {self.get_field().related_model} with {self.related_field_name} {data} "
                    f"does not exist: {e}"
                )
            else:
                return None
        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"The data {data} for model {self.get_field().related_model} has an incorrect type "
                f"{type(data).__name__}: {e}"
            )


class UUIDRelatedField(RelatedField):
    default_related_field_name = "uid"

    def to_representation(self, related_obj: models.Model) -> None | str:
        _ = super().to_representation(related_obj)
        return serializers.UUIDField().to_representation(related_obj)

    def to_internal_value(self, data: str) -> models.Model | None:
        uuid = data
        if uuid:
            uuid = serializers.UUIDField().to_internal_value(data)
        return super().to_internal_value(uuid)


class ExternalUUIDRelatedField(UUIDRelatedField):
    default_related_field_name = "external_uid"
