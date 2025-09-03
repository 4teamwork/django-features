from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.safestring import SafeString

from django_features.system_message import forms
from django_features.system_message import models


@admin.register(models.SystemMessageType)
class SystemInfoTypeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "icon",
    )
    list_display_links = ["id", "name"]
    search_fields = [
        "id",
        "name",
        "icon",
    ]


@admin.register(models.SystemMessage)
class SystemInfoAdmin(admin.ModelAdmin):
    form = forms.SystemMessageAdminForm
    list_display = (
        "id",
        "__str__",
        "type",
        "get_background_preview",
        "background_color",
        "get_text_preview",
        "text_color",
    )
    list_display_links = ["id", "__str__"]
    list_filter = ("type",)
    search_fields = [
        "background_color",
        "text",
        "id",
        "text_color",
        "title",
        "type",
    ]

    def get_background_preview(self, obj: models.SystemMessage) -> SafeString:
        return mark_safe(
            f"<div style='background-color: {obj.background_color}; width: 20px;'>&nbsp;</div>"
        )

    def get_text_preview(self, obj: models.SystemMessage) -> SafeString:
        return mark_safe(
            f"<div style='background-color: {obj.text_color}; width: 20px;'>&nbsp;</div>"
        )
