from factory import SubFactory  # type: ignore

from django_features.custom_fields import models
from django_features.system_message.factories import BaseFactory  # type: ignore


class CustomFieldFactory(BaseFactory):
    class Meta:
        model = models.CustomField

    field_type = models.CustomField.FIELD_TYPES.CHAR
    identifier = "custom_field"
    label_de = "Custom Field Label"


class CustomValueFactory(BaseFactory):
    class Meta:
        model = models.CustomValue

    field = SubFactory(CustomFieldFactory)  # type: ignore
    value = "custom value"
