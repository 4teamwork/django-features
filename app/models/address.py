from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django_features.custom_fields.models import CustomFieldBaseModel


class Address(CustomFieldBaseModel):
    city = models.CharField(verbose_name="city", blank=True)
    country = models.CharField(verbose_name="country", blank=True)
    street = models.CharField(verbose_name="street", blank=True)
    external_uid = models.UUIDField(verbose_name="external uid", null=True)
    zip_code = models.CharField(verbose_name="postal code", blank=True)

    target = GenericForeignKey("target_type", "target_id")
    target_type = models.ForeignKey(
        ContentType, blank=True, null=True, on_delete=models.CASCADE
    )
    target_id = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self) -> str:
        return f"{self.street} {self.zip_code} {self.city}".strip()
