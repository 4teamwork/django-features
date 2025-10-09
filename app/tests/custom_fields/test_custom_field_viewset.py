from django.contrib.contenttypes.models import ContentType
from pluck import pluck

from app.models import Address
from app.models import Person
from app.tests import APITestCase
from app.tests.custom_fields.factories import CustomFieldFactory


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
