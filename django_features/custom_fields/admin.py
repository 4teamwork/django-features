from typing import Any

from django.conf import settings
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from modeltranslation.admin import TranslationAdmin

from django_features.custom_fields import models
from django_features.custom_fields.models import CustomFieldBaseModel
from django_features.custom_fields.models import CustomFieldTypeBaseModel


class CustomFieldBaseAdmin(TranslationAdmin):
    def has_module_permission(self, request: HttpRequest) -> bool:
        return settings.CUSTOM_FIELDS_FEATURE

    def get_form(self, request: HttpRequest, obj: Any = None, **kwargs: Any) -> Any:
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["content_type"].queryset = ContentType.objects.filter(
            id__in=[
                content_type.id
                for content_type in ContentType.objects.all()
                if content_type.model_class() is not None
                and issubclass(content_type.model_class(), CustomFieldBaseModel)
            ]
        )
        form.base_fields["type_content_type"].queryset = ContentType.objects.filter(
            id__in=[
                content_type.id
                for content_type in ContentType.objects.all()
                if content_type.model_class() is not None
                and issubclass(content_type.model_class(), CustomFieldTypeBaseModel)
            ]
        )
        return form

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> list[str]:
        if obj:
            return [*self.readonly_fields, "field_type"]
        return self.readonly_fields


@admin.register(models.CustomField)
class CustomFieldAdmin(CustomFieldBaseAdmin):
    list_display = ["id", "identifier", "__str__", "field_type"]
    list_display_links = (
        "id",
        "identifier",
        "__str__",
    )
    list_filter = ("choice_field", "editable", "field_type", "content_type")
    search_fields = ("label", "identifier")


@admin.register(models.CustomValue)
class ValueAdmin(TranslationAdmin):
    list_display = ["id", "__str__"]
    search_fields = ("label", "value", "field__label", "field__identifier")
