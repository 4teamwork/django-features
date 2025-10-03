from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class SystemMessageType(TimeStampedModel):
    name = models.CharField(verbose_name=_("Name"), max_length=32)
    icon = models.CharField(
        verbose_name=_("Icon"),
        help_text=_("Icon Name von mdi ohne mdi-Prefix mit Bindestrich getrennt"),
        max_length=255,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Systemmeldungstyp")
        verbose_name_plural = _("Systemmeldungstypen")
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name}"


class SystemMessage(TimeStampedModel):
    background_color = models.CharField(
        verbose_name=_("Hintergrundfarbe"), default="#0000FF", max_length=7
    )
    begin = models.DateTimeField(verbose_name=_("Beginn"))
    end = models.DateTimeField(verbose_name=_("Ende"), blank=True, null=True)
    order = models.PositiveIntegerField(_("Reihenfolge"), default=0)
    text = models.TextField(verbose_name=_("Nachricht"), blank=True)
    text_color = models.CharField(
        verbose_name=_("Textfarbe"), default="#000000", max_length=7
    )
    title = models.CharField(verbose_name=_("Titel"), max_length=32)
    type = models.ForeignKey(
        SystemMessageType,
        on_delete=models.PROTECT,
        related_name="system_messages",
        verbose_name=_("Typ"),
    )
    dismissed_users = models.ManyToManyField(
        get_user_model(),
        related_name="dismissed_system_messages",
        blank=True,
    )

    class Meta:
        verbose_name = _("Systemmeldung")
        verbose_name_plural = _("Systemmeldungen")
        ordering = ("order", "end", "begin", "title")

    def __str__(self) -> str:
        return f"{self.title}"
