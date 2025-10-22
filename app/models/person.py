from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from django_features.custom_fields.models import CustomFieldBaseModel
from django_features.custom_fields.models.base import CustomFieldTypeBaseModel


class PersonType(CustomFieldTypeBaseModel):
    title = models.CharField(verbose_name="title", max_length=255)

    class Meta:
        verbose_name = "Person type"
        verbose_name_plural = "Person types"


class Person(CustomFieldBaseModel):
    _custom_field_type_attr = "person_type"

    addresses = GenericRelation("Address", "target_id", "target_type")
    firstname = models.CharField(verbose_name="firstname")
    lastname = models.CharField(verbose_name="lastname", null=True, blank=True)
    email = models.EmailField(verbose_name="email", null=True, blank=True)
    person_type = models.ForeignKey(
        PersonType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Type",
    )
    place_of_residence = models.ForeignKey(
        "Municipality",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Place of residence",
        related_name="persons",
    )

    class Meta:
        verbose_name = "Person"
        verbose_name_plural = "Persons"

    def __str__(self) -> str:
        if not self.lastname:
            return self.firstname
        return f"{self.firstname} {self.lastname}"
