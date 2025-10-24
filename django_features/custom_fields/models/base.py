from typing import Any

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.expressions import ArraySubquery
from django.db import IntegrityError
from django.db import models
from django.db import ProgrammingError
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast
from django.db.models.functions import JSONObject
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from django_features.custom_fields.models.field import CustomField
from django_features.custom_fields.models.field import CustomFieldQuerySet
from django_features.custom_fields.models.value import CustomValue


class CustomFieldModelBaseManager(models.Manager):
    def get_type_model(self) -> "CustomFieldTypeBaseModel | None":
        if self.model._custom_field_type_attr is None or not hasattr(
            self.model, self.model._custom_field_type_attr
        ):
            return None
        return getattr(
            self.model, self.model._custom_field_type_attr
        ).field.related_model

    def get_type_filter(self) -> Q:
        type_model = self.get_type_model()
        if type_model is not None:
            type_filter = {
                "type_content_type__app_label": type_model._meta.app_label,
                "type_content_type__model": type_model._meta.model_name,
                "type_id": OuterRef(f"{self.model._custom_field_type_attr}_id"),
            }
            return Q(**type_filter) | Q(type_id__isnull=True)
        return Q()

    def _subquery(self, field: CustomField) -> Subquery:
        pk_filter = {
            f"{self.model._meta.model_name}__id": OuterRef("pk"),
        }

        custom_values_queryset = CustomValue.objects.for_model(self.model).filter(
            **pk_filter, field__identifier=field.identifier
        )

        if not field.choice_field:
            return Subquery(
                custom_values_queryset.annotate(
                    formated=Cast(
                        (
                            RawSQL(
                                f"ARRAY(SELECT (jsonb_array_elements_text(value))::{field.sql_field})",
                                [],
                            )
                            if field.multiple
                            else RawSQL("(value #>> '{}')", [])
                        ),
                        output_field=field.output_field,
                    )
                ).values_list("formated", flat=True)
            )
        else:
            sq = ArraySubquery if field.multiple else Subquery
            return sq(
                custom_values_queryset.annotate(
                    formated=JSONObject(id="id", label="label", value="value")
                ).values_list("formated", flat=True)
            )

    def get_queryset(self) -> QuerySet:
        """
        We filter all available custom fields for the current model.
        """
        try:
            available_fields = CustomField.objects.for_model(self.model)

            """
            This for loop creates a dict with all available custom field values with a subquery for the specific object.
            The dict key is the identifier of the custom field amd the value is the custom value.
            If the object has no value for the field, it will return None.
            More information can be found in the django documentation:
            https://docs.djangoproject.com/en/5.2/ref/models/expressions/#subquery-expressions
            """
            fields = {
                field.identifier: self._subquery(field) for field in available_fields
            }

            """
            # The dict can be unpacked and used for the dynamic annotations.
            # We also annotate the available custom field identifiers as 'custom_field_keys'.
            # Therefore, we know which custom fields are available for this object.
            """
            return (
                super()
                .get_queryset()
                .annotate(**fields)
                .annotate(
                    custom_field_keys=ArraySubquery(
                        available_fields.filter(self.get_type_filter()).values_list(
                            "identifier", flat=True
                        )
                    )
                )
            )
        except (ProgrammingError, RuntimeError, IntegrityError):
            return super().get_queryset()


class CustomFieldTypeBaseModel(TimeStampedModel):
    custom_fields = GenericRelation(
        CustomField, object_id_field="type_id", content_type_field="type_content_type"
    )

    class Meta:
        abstract = True


class CustomFieldBaseModel(TimeStampedModel):
    _custom_field_type_attr: str | None = None

    custom_values = models.ManyToManyField(
        blank=True,
        to=CustomValue,
        verbose_name=_("Benutzerdefinierte Werte"),
    )
    objects = CustomFieldModelBaseManager()

    class Meta:
        abstract = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.handle_custom_values = True

        self._custom_values_to_delete: list[int] = []
        self._custom_values_to_remove: list[CustomValue] = []
        self._custom_values_to_save: list[CustomValue] = []

    def _save_custom_values(self) -> None:
        if self._custom_values_to_remove:
            self.custom_values.remove(*self._custom_values_to_remove)

        if self._custom_values_to_delete:
            self.custom_values.filter(id__in=self._custom_values_to_delete).delete()

        _custom_values_to_add: set[CustomValue] = set()
        existing_custom_values = self.custom_values.all()
        for value in self._custom_values_to_save:
            value.save()  # type: ignore
            if value not in existing_custom_values:
                _custom_values_to_add.add(value)
        if _custom_values_to_add:
            self.custom_values.add(*_custom_values_to_add)
        self._custom_values_to_save = []
        self._custom_values_to_remove = []

    def save(self, **kwargs: Any) -> None:
        super().save(**kwargs)  # type: ignore
        if self.handle_custom_values:
            self._save_custom_values()

    def refresh_with_custom_fields(self) -> None:
        if self.pk is None:
            return
        self.__dict__.update(self.__class__.objects.get(pk=self.pk).__dict__)

    def _create_or_update_custom_value(self, field: str, value: Any) -> None:
        try:
            value_object = self.custom_values.select_related("field").get(field=field)
            if value is None:
                self._custom_values_to_delete.append(value_object.id)
                return
        except CustomValue.DoesNotExist:
            value_object = CustomValue(field=field)
        serializer_field = value_object.field.serializer_field
        serializer_field.run_validators(value)
        value_object.value = serializer_field.to_representation(value)
        self._custom_values_to_save.append(value_object)

    def _set_choice_value(self, field: CustomField, value: Any) -> None:
        self._custom_values_to_remove.extend(CustomValue.objects.filter(field=field))
        if value is None:
            return
        if field.multiple:
            # We expect a list for multiple choice fields, so we must extend the list with the items of the list
            self._custom_values_to_save.extend(value)
        else:
            self._custom_values_to_save.append(value)

    def set_custom_attr(self, name: str, value: Any) -> None:
        if not hasattr(self, "custom_field_keys"):
            self.refresh_with_custom_fields()
        self.__setattr__(name, value)

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, "custom_field_keys") and name in self.custom_field_keys:
            field = CustomField.objects.get(identifier=name)
            if field.choice_field:
                self._set_choice_value(field, value)
            else:
                self._create_or_update_custom_value(field, value)
        super().__setattr__(name, value)

    def delete(
        self,
        using: Any | None = None,
        keep_parents: bool = False,
        delete_custom_values: bool = True,
    ) -> None:
        if delete_custom_values:
            self.custom_values.filter(field__choice_field=False).delete()
        super().delete(using, keep_parents)

    @property
    def custom_fields(self) -> CustomFieldQuerySet:
        return CustomField.objects.for_model(self.__class__)

    @property
    def custom_field_type(self) -> CustomFieldTypeBaseModel | None:
        if self._custom_field_type_attr and hasattr(self, self._custom_field_type_attr):
            return getattr(self, self._custom_field_type_attr)
        return None

    @property
    def default_custom_fields(self) -> CustomFieldQuerySet:
        return CustomField.objects.default_for(self.__class__)

    @property
    def type_custom_fields(self) -> CustomFieldQuerySet:
        if self.custom_field_type:
            return self.custom_field_type.custom_fields.all()
        return CustomField.objects.none()
