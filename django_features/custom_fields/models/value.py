from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from django_features.custom_fields.models.field import CustomField


class CustomValueQuerySet(models.QuerySet):
    def for_model(self, model: type[models.Model]) -> "CustomValueQuerySet":
        return self.select_related("field", "field__content_type").filter(
            field__content_type__app_label=model._meta.app_label,
            field__content_type__model=model._meta.model_name,
        )

    def for_type(self, model: type[models.Model]) -> "CustomValueQuerySet":
        return self.select_related("content_type").filter(
            field__type_content_type__app_label=model._meta.app_label,
            field__type_content_type__model=model._meta.model_name,
        )

    def default(self) -> "CustomValueQuerySet":
        return self.filter(field__type_id__isnull=True)

    def default_for(self, model: type[models.Model]) -> "CustomValueQuerySet":
        return self.for_model(model).default()


class CustomValue(TimeStampedModel):
    field = models.ForeignKey(
        CustomField,
        related_name="values",
        verbose_name=_("Feld"),
        on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField(_("Reihenfolge"), default=0)
    label = models.CharField(verbose_name=_("Label"), null=True, blank=True)
    value = models.JSONField(verbose_name=_("Wert"), null=True, blank=True)

    objects = CustomValueQuerySet.as_manager()

    class Meta:
        ordering = ["order", "created"]
        verbose_name = _("Benutzerdefinierter Wert")
        verbose_name_plural = _("Benutzerdefinierte Werte")

    def __str__(self) -> str:
        return self.text or ""

    @property
    def text(self) -> str:
        return self.label or str(self.value)
