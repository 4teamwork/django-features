from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from app.custom_field import models
from django_features.custom_fields.admin import BaseAdmin
from django_features.custom_fields.admin import CustomFieldBaseAdmin


@admin.register(models.CustomField)
class CustomFieldAdmin(BaseAdmin, CustomFieldBaseAdmin, TranslationAdmin):
    list_display = ["id", "identifier", "__str__", "field_type", "filterable"]
    list_display_links = (
        "id",
        "identifier",
        "__str__",
    )
    list_filter = (
        "choice_field",
        "content_type",
        "editable",
        "field_type",
        "filterable",
    )
    search_fields = ("label", "identifier")


@admin.register(models.CustomValue)
class ValueAdmin(BaseAdmin, TranslationAdmin):
    list_display = ["id", "__str__"]
    search_fields = ("label", "value", "field__label", "field__identifier")
