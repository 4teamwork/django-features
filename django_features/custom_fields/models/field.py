import logging
from copy import deepcopy
from typing import Any

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from rest_framework import serializers

from django_features.custom_fields.models.value import CustomValueQuerySet


logger = logging.getLogger("django_features.custom_fields")


class CustomFieldCreateOnlyDefault(serializers.CreateOnlyDefault):
    def __call__(self, serializer_field: serializers.Field) -> Any:
        # Standalone model-provided fields remain usable for creation validation.
        if serializer_field.parent is None:
            return self.default() if callable(self.default) else self.default
        return super().__call__(serializer_field)


def warn_invalid_default(field: "AbstractBaseCustomField") -> None:
    # Configuration may contain personal data: never include values or exceptions.
    logger.warning(
        "Ignoring invalid custom field default configuration.",
        extra={
            "custom_field_model": field._meta.label_lower,
            "custom_field_pk": field.pk,
            "code": "invalid_custom_field_default",
        },
    )


class CustomFieldQuerySet(models.QuerySet):
    def with_choices(self) -> "CustomFieldQuerySet":
        from django_features.custom_fields.helpers import get_custom_value_model

        value_model = get_custom_value_model()
        accessor = value_model._meta.get_field("field").remote_field.get_accessor_name()
        return self.prefetch_related(
            models.Prefetch(
                accessor,
                queryset=value_model.objects.filter(field__choice_field=True),
                to_attr="_prefetched_choices",
            )
        )

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

    def filterable(self) -> "CustomFieldQuerySet":
        return self.filter(filterable=True)


class FieldType:
    CHAR = "CHAR"
    TEXT = "TEXT"
    DATE = "DATE"
    DATETIME = "DATETIME"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"


class AbstractBaseCustomField(TimeStampedModel):
    FIELD_TYPES = FieldType

    BLANK_TYPES = (
        FIELD_TYPES.CHAR,
        FIELD_TYPES.TEXT,
    )

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
    filterable = models.BooleanField(
        verbose_name=_("Als Filter anbieten"),
        default=False,
    )
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
        abstract = True

    def __str__(self) -> str:
        return f"{self.label}"

    @property
    def choices(self) -> CustomValueQuerySet | list:
        from django_features.custom_fields.helpers import get_custom_value_model

        custom_value_model = get_custom_value_model()
        if not self.choice_field or self.pk is None:
            return custom_value_model.objects.none()
        if hasattr(self, "_prefetched_choices"):
            return self._prefetched_choices
        accessor = custom_value_model._meta.get_field(
            "field"
        ).remote_field.get_accessor_name()
        cache = getattr(self, "_prefetched_objects_cache", {})
        if accessor in cache:
            return cache[accessor]
        return custom_value_model.objects.filter(field=self)

    @property
    def output_field(self) -> models.Field:
        from django_features.custom_fields.helpers import get_custom_field_model

        output_field = get_custom_field_model().TYPE_FIELD_MAP.get(self.field_type)
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
        result = self._serializer_field()
        if self.default is not None and not self.required:
            if self.choice_field:
                result.default = CustomFieldCreateOnlyDefault(self.default)
            else:

                def get_default() -> Any:
                    try:
                        return deepcopy(result.run_validation(self.default))
                    except serializers.ValidationError:
                        # Skip subsequent defaults on this field without logging again.
                        result.default = serializers.empty
                        warn_invalid_default(self)
                        raise serializers.SkipField() from None

                result.default = CustomFieldCreateOnlyDefault(get_default)
        return result

    def validate_default(
        self, *, choices: Any = None, validate_choices: bool = True
    ) -> Any:
        """Validate configured defaults strictly, including defaults on required fields."""
        if self.default is None or (self.choice_field and not validate_choices):
            return None
        if self.field_type not in self.TYPE_SERIALIZER_MAP:
            raise ValidationError(
                {"field_type": _("Wählen Sie einen unterstützten Feldtyp.")}
            )
        if choices is not None:
            # Pending inline additions have no canonical ID until they are saved.
            # They still participate in the caller's mapping/duplicate validation.
            choices = [choice for choice in choices if choice.pk is not None]
        try:
            return self._serializer_field(choices=choices).run_validation(self.default)
        except serializers.ValidationError as exc:
            raise ValidationError(
                {"default": _("Der Standardwert entspricht nicht den Feldregeln.")}
            ) from exc

    def clean(self, *, validate_choices: bool = True) -> None:
        super().clean()
        self.validate_default(validate_choices=validate_choices)

    def _serializer_field(self, *, choices: Any = None) -> serializers.Field:
        from django_features.custom_fields.fields import ChoiceIdField

        params: dict[str, Any] = {
            "allow_null": self.allow_null,
            "required": self.required,
        }
        if self.choice_field:
            return ChoiceIdField(field=self, choices=choices, **params)

        serializer_field = self.TYPE_SERIALIZER_MAP.get(self.field_type)
        if serializer_field is None:
            raise ValueError(f"Unknown field type: {self.field_type}")

        child_params = {"allow_null": self.allow_null}
        if self.field_type in self.BLANK_TYPES:
            child_params["allow_blank"] = self.allow_blank
        if self.multiple:
            result = serializers.ListField(
                child=serializer_field(**child_params),
                allow_empty=self.allow_blank,
                **params,
            )
        else:
            result = serializer_field(**{**params, **child_params})
        return result

    @property
    def sql_field(self) -> str:
        sql_field = self.TYPE_SQL_MAP.get(self.field_type)
        if not sql_field:
            raise ValueError(f"Unknown field type: {self.field_type}")
        return sql_field
