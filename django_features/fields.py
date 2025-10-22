from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class UUIDRelatedField(serializers.RelatedField):
    """
    A relation field which expects an uid to be present on the related model for lookup and representation.
    """

    default_uuid_field_name = "uid"

    default_error_messages = {
        "does_not_exist": _("Objekt existiert nicht."),
        "incorrect_type": _("Inkorrekter Typ."),
    }

    def __init__(
        self,
        field: models.Field | None = None,
        queryset: QuerySet | None = None,
        uuid_field_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.field = field
        self.queryset = queryset
        self.uuid_field_name = uuid_field_name or self.default_uuid_field_name
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
        Get the UID of the related object; format it as UID.
        """
        if not related_obj:
            return None
        related_uid = getattr(related_obj, self.uuid_field_name)
        if related_uid is None:
            raise AttributeError(
                f"No field named 'UID' defined for relation to {self.field_name} on {related_obj}"
            )
        return serializers.UUIDField().to_representation(related_uid)

    def to_internal_value(self, data: str) -> models.Model | None:
        """
        Assume that the model is defined on the serializer using this field.
        """
        if not data and not self.required:
            return None
        uid = serializers.UUIDField().to_internal_value(data)
        try:
            return self.get_queryset().get(**{self.uuid_field_name: uid})
        except ObjectDoesNotExist as e:
            raise ValidationError(
                f"Object {self.get_field().related_model} with uid {uid} does not exist: {e}"
            )
        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"The data {uid} for model {self.get_field().related_model} has an incorrect type {type(data).__name__}: {e}"
            )
