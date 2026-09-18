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
        constraints = [
            models.UniqueConstraint(
                fields=["field", "external_label"],
                condition=~models.Q(external_label=""),
                name="custom_value_field_external_label_unique",
            )
        ]
        ordering = ["order", "created"]
        verbose_name = _("Benutzerdefinierter Wert")
        verbose_name_plural = _("Benutzerdefinierte Werte")
