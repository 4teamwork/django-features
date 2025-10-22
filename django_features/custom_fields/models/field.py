from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from rest_framework import serializers


class CustomFieldQuerySet(models.QuerySet):
    def for_model(self, model: type[models.Model]) -> "CustomFieldQuerySet":
        return self.select_related("content_type").filter(
            content_type__app_label=model._meta.app_label,
            content_type__model=model._meta.model_name,
        )

    def for_type(self, model: type[models.Model]) -> "CustomFieldQuerySet":
        return self.select_related("content_type").filter(
            type_content_type__app_label=model._meta.app_label,
            type_content_type__model=model._meta.model_name,
        )

    def default(self) -> "CustomFieldQuerySet":
        return self.filter(type_id__isnull=True)

    def default_for(self, model: type[models.Model]) -> "CustomFieldQuerySet":
        return self.for_model(model).default()


class FieldType:
    CHAR = "CHAR"
    TEXT = "TEXT"
    DATE = "DATE"
    DATETIME = "DATETIME"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"


class CustomField(TimeStampedModel):
    FIELD_TYPES = FieldType

    TYPE_SQL_MAP = {
        FIELD_TYPES.CHAR: "char",
        FIELD_TYPES.TEXT: "text",
        FIELD_TYPES.DATE: "date",
        FIELD_TYPES.DATETIME: "datetime",
        FIELD_TYPES.INTEGER: "integer",
        FIELD_TYPES.BOOLEAN: "boolean",
    }

    TYPE_FIELD_MAP = {
        FIELD_TYPES.CHAR: models.CharField,
        FIELD_TYPES.TEXT: models.TextField,
        FIELD_TYPES.DATE: models.DateField,
        FIELD_TYPES.DATETIME: models.DateTimeField,
        FIELD_TYPES.INTEGER: models.IntegerField,
        FIELD_TYPES.BOOLEAN: models.BooleanField,
    }

    TYPE_SERIALIZER_MAP = {
        FIELD_TYPES.CHAR: serializers.CharField,
        FIELD_TYPES.TEXT: serializers.CharField,
        FIELD_TYPES.DATE: serializers.DateField,
        FIELD_TYPES.DATETIME: serializers.DateTimeField,
        FIELD_TYPES.INTEGER: serializers.IntegerField,
        FIELD_TYPES.BOOLEAN: serializers.BooleanField,
    }

    TYPE_CHOICES = [
        (FIELD_TYPES.CHAR, _("Text (einzeilig)")),
        (FIELD_TYPES.TEXT, _("Text (mehrzeilig)")),
        (FIELD_TYPES.DATE, _("Datum")),
        (FIELD_TYPES.DATETIME, _("Datum und Zeit")),
        (FIELD_TYPES.INTEGER, _("Zahl (Ganzzahl)")),
        (FIELD_TYPES.BOOLEAN, _("Checkbox")),
    ]

    allow_blank = models.BooleanField(
        verbose_name=_("Leeren String erlauben"), default=True
    )
    allow_null = models.BooleanField(
        verbose_name=_("Leere Werte erlauben"), default=True
    )
    choice_field = models.BooleanField(verbose_name=_("Auswahlfeld"), default=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    default = models.JSONField(verbose_name=_("Standardwert"), null=True, blank=True)
    editable = models.BooleanField(verbose_name=_("Editierbar"), default=True)
    external_key = models.CharField(
        verbose_name=_("Externer Key"), blank=True, null=True
    )
    field_type = models.CharField(verbose_name=_("Feldtyp"), choices=TYPE_CHOICES)
    hidden = models.BooleanField(verbose_name=_("Ausblenden"), default=False)
    identifier = models.SlugField(max_length=64, unique=True, db_index=True)
    label = models.CharField(verbose_name=_("Name"))
    multiple = models.BooleanField(verbose_name=_("Liste"), default=False)
    order = models.PositiveSmallIntegerField(verbose_name=_("Reihenfolge"), default=0)
    required = models.BooleanField(verbose_name=_("Erforderlich"), default=False)

    type_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        related_name="customfield_set_for_type",
        blank=True,
        null=True,
    )
    type_id = models.PositiveIntegerField(null=True, blank=True)
    type_object = GenericForeignKey(ct_field="type_content_type", fk_field="type_id")

    objects = CustomFieldQuerySet.as_manager()

    class Meta:
        verbose_name = _("Benutzerdefiniertes Feld")
        verbose_name_plural = _("Benutzerdefinierte Felder")
        ordering = ["order", "created"]

    def __str__(self) -> str:
        return f"{self.label}"

    @property
    def choices(self) -> list[tuple[str, str]]:
        from django_features.custom_fields.models import CustomValue

        if not self.choice_field:
            return CustomValue.objects.none()
        return CustomValue.objects.filter(field=self)

    @property
    def output_field(self) -> models.Field:
        output_field = CustomField.TYPE_FIELD_MAP.get(self.field_type)
        if not output_field:
            raise ValueError(f"Unknown field type: {self.field_type}")

        if self.multiple:
            return ArrayField(
                base_field=output_field(blank=self.allow_blank, null=self.allow_null),
                default=self.default,
            )
        return output_field(
            blank=self.allow_blank, null=self.allow_null, default=self.default
        )

    @property
    def serializer_field(self) -> serializers.Field:
        from django_features.custom_fields.fields import ChoiceIdField

        if self.choice_field:
            return ChoiceIdField(field=self)

        serializer_field = self.TYPE_SERIALIZER_MAP.get(self.field_type)
        if serializer_field is None:
            raise ValueError(f"Unknown field type: {self.field_type}")

        params = {"allow_null": self.allow_null}
        if self.default and not self.required:
            params["default"] = self.default
        else:
            params["required"] = self.required

        if self.multiple:
            return serializers.ListField(child=serializer_field(**params), **params)

        return serializer_field(**params)

    @property
    def sql_field(self) -> str:
        sql_field = self.TYPE_SQL_MAP.get(self.field_type)
        if not sql_field:
            raise ValueError(f"Unknown field type: {self.field_type}")
        return sql_field
