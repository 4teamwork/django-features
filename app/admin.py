from django.contrib import admin

from app import models


@admin.register(models.Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("id", "__str__")
    list_display_links = ("id", "__str__")
    search_fields = ("city", "country", "street", "zip_code")


@admin.register(models.Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("id", "__str__", "email")
    list_display_links = ("id", "__str__")
    search_fields = ("email", "firstname", "lastname")
