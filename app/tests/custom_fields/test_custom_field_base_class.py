from django.db.models import QuerySet
from django_extensions.db.models import TimeStampedModel

from app.tests import APITestCase
from app.web.publishable import PublishableModel
from app.web.publishable import PublishableQuerySet
from django_features.custom_fields import models
from django_features.custom_fields.factories import CustomFieldFactory
from django_features.custom_fields.models.field import CustomFieldQuerySet


class CustomFieldBaseClassTestCase(APITestCase):
    def test_custom_field_base_model_class(self) -> None:
        self.assertTrue(issubclass(models.CustomField, TimeStampedModel))
        self.assertTrue(issubclass(models.CustomField, PublishableModel))

    def test_edit_custom_field_base_model_class_field(self) -> None:
        custom_field: models.CustomField = CustomFieldFactory()  # type: ignore
        self.assertFalse(custom_field.is_public)
        custom_field.is_public = True
        self.assertTrue(custom_field.is_public)

    def test_custom_field_base_queryset_class(self) -> None:
        self.assertTrue(issubclass(CustomFieldQuerySet, QuerySet))
        self.assertTrue(issubclass(CustomFieldQuerySet, PublishableQuerySet))

    def test_publishable_custom_field_base_queryset_class(self) -> None:
        CustomFieldFactory(identifier="field_1")
        CustomFieldFactory(identifier="field_2", is_public=True)
        CustomFieldFactory(identifier="field_3", is_public=True)
        self.assertEqual(3, models.CustomField.objects.all().count())
        self.assertEqual(2, models.CustomField.objects.publishable().count())
        self.assertEqual(1, models.CustomField.objects.filter(is_public=False).count())
