from django.contrib.contenttypes.models import ContentType
from factory import lazy_attribute  # type: ignore
from factory import SubFactory  # type: ignore
from factory.django import DjangoModelFactory

from django_features.custom_fields import models


class CustomFieldFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomField

    @lazy_attribute
    def content_type(self) -> ContentType | None:
        try:
            from app.models import Person

            return ContentType.objects.get_for_model(Person)
        except ModuleNotFoundError:
            return None

    field_type = models.CustomField.FIELD_TYPES.CHAR
    identifier = "custom_field"
    label_de = "Custom Field Label"


class CustomValueFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    field = SubFactory(CustomFieldFactory)  # type: ignore
    value = "custom value"


class CustomChoiceFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    label_de = "Red"
    value = "red"


class CustomTextValueFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    value = "Custom text"


class CustomDateValueFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    value = "2019-01-01"


class CustomIntegerValueFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    value = 1


class CustomBooleanValueFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    value = True


class CustomArrayValueFactory(DjangoModelFactory):
    class Meta:
        model = models.CustomValue

    value = [1, 2, 3]
