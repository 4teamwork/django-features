from django.contrib.contenttypes.models import ContentType
from pluck import pluck
from rest_framework.test import APIRequestFactory

from app.custom_field.tests.factories import CustomFieldFactory
from app.models import Address
from app.models import Person
from app.models import PersonType
from app.tests import APITestCase
from django_features.custom_fields.viewsets import CustomFieldViewSet


class CustomFieldViewSetTest(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.cs1 = CustomFieldFactory(
            identifier="custom_field_person",
            content_type=ContentType.objects.get_for_model(Person),
        )
        self.cs2 = CustomFieldFactory(
            identifier="custom_field_address",
            content_type=ContentType.objects.get_for_model(Address),
        )

    def test_custom_field_viewset_without_filter(self) -> None:
        response = self.client.get("/api/custom_field")

        data = response.json()
        self.assertEqual(2, len(data))
        self.assertEqual(
            ["custom_field_person", "custom_field_address"], pluck(data, "identifier")
        )

    def test_custom_field_viewset_with_model_filter(self) -> None:
        response = self.client.get("/api/custom_field?model=Person")

        data = response.json()

        self.assertEqual(1, len(data))
        self.assertEqual(["custom_field_person"], pluck(data, "identifier"))

    def test_custom_field_viewset_with_app_filter(self) -> None:
        response = self.client.get("/api/custom_field?app_label=App")

        data = response.json()
        self.assertEqual(2, len(data))
        self.assertEqual(
            ["custom_field_person", "custom_field_address"], pluck(data, "identifier")
        )

        response = self.client.get("/api/custom_field?app_label=bla")

        data = response.json()
        self.assertEqual(0, len(data))

    def test_queryset_selects_type_content_type(self) -> None:
        person_type = PersonType.objects.create(title="Employee")
        self.cs1.type_content_type = ContentType.objects.get_for_model(PersonType)
        self.cs1.type_id = person_type.pk
        self.cs1.save(update_fields=["type_content_type", "type_id"])
        view = CustomFieldViewSet()
        view.request = APIRequestFactory().get("/api/custom_field")

        with self.assertNumQueries(1):
            custom_fields = list(view.get_queryset())
        with self.assertNumQueries(0):
            metadata = [
                (
                    custom_field.type_content_type.app_label,
                    custom_field.type_content_type.model,
                )
                for custom_field in custom_fields
                if custom_field.type_content_type is not None
            ]

        self.assertEqual([("app", "persontype")], metadata)
