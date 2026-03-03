from django.db import models
from django.utils.translation import gettext_lazy as _

from app.custom_field.models.field import CustomField
from django_features.custom_fields.models.value import AbstractBaseCustomValue


class CustomValue(AbstractBaseCustomValue):
    field = models.ForeignKey(
        CustomField,
        related_name="values",
        verbose_name=_("Feld"),
        on_delete=models.CASCADE,
    )

    class Meta:
        ordering = ["order", "created"]
        verbose_name = _("Benutzerdefinierter Wert")
        verbose_name_plural = _("Benutzerdefinierte Werte")
