from factory import SubFactory  # type: ignore
from factory.django import DjangoModelFactory

from django_features.custom_fields import models


class CustomFieldFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomField

    field_type = models.CustomField.FIELD_TYPES.CHAR
    identifier = "custom_field"
    label_de = "Custom Field Label"


class CustomValueFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    field = SubFactory(CustomFieldFactory)  # type: ignore
    value = "custom value"
