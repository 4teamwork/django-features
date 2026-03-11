from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _

from app.custom_field.models import CustomField
from app.custom_field.models import CustomValue
from django_features.custom_fields.models.base import CustomFieldBaseModel
from django_features.custom_fields.models.base import CustomFieldTypeBaseModel


class CustomTypeBaseModel(CustomFieldTypeBaseModel):
    custom_fields = GenericRelation(
        CustomField,
        object_id_field="type_id",
        content_type_field="type_content_type",
    )

    class Meta:
        abstract = True


class CustomBaseModel(CustomFieldBaseModel):
    custom_values = models.ManyToManyField(
        blank=True,
        to=CustomValue,
        verbose_name=_("Benutzerdefinierte Werte"),
    )

    class Meta:
        abstract = True
