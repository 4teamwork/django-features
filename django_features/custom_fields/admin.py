from typing import Any

from django.conf import settings
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest

from django_features.custom_fields.models import CustomFieldBaseModel
from django_features.custom_fields.models import CustomFieldTypeBaseModel


class BaseAdmin(admin.ModelAdmin):
    def has_module_permission(self, request: HttpRequest) -> bool:
        return settings.CUSTOM_FIELD_ADMIN and settings.CUSTOM_FIELDS_FEATURE


class CustomFieldBaseAdmin(admin.ModelAdmin):
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
