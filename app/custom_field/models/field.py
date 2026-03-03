from django.utils.translation import gettext_lazy as _

from django_features.custom_fields.models.field import AbstractBaseCustomField


class CustomField(AbstractBaseCustomField):
    class Meta:
        verbose_name = _("Benutzerdefiniertes Feld")
        verbose_name_plural = _("Benutzerdefinierte Felder")
        ordering = ["order", "created"]
