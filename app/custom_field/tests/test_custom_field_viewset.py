from django.contrib.contenttypes.models import ContentType
from pluck import pluck

from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.models import Address
from app.models import Person
from app.tests import APITestCase


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

    def test_populated_choices_have_constant_endpoint_query_budget(self) -> None:
        self.cs1.choice_field = True
        self.cs1.save()
        fields = [self.cs1]
        for count in [1, 12]:
            while len(fields) < count:
                fields.append(
                    CustomFieldFactory(
                        identifier=f"choice_{len(fields)}",
                        choice_field=True,
                        content_type=self.cs1.content_type,
                    )
                )
            for field in fields:
                if not field.values.exists():
                    for index in range(3):
                        CustomValueFactory(field=field, value=f"choice-{index}")
            # Two auth/session queries, transaction boundaries, and two data queries.
            with self.assertNumQueries(6):
                response = self.client.get("/api/custom_field?model=Person")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(len(data), count)
            self.assertTrue(all(len(field["choices"]) == 3 for field in data))
            self.assertTrue(
                all(
                    set(choice) == {"id", "label", "value"}
                    for field in data
                    for choice in field["choices"]
                )
            )

    def test_choice_metadata_preserves_valid_defaults_and_loads_choices_once(
        self,
    ) -> None:
        from django_features.custom_fields.serializers import CustomFieldSerializer

        for multiple, empty in [(False, False), (True, False), (True, True)]:
            field = CustomFieldFactory(
                identifier=f"default_{multiple}_{empty}",
                choice_field=True,
                multiple=multiple,
            )
            choice = CustomValueFactory(field=field, value="valid")
            field.default = ([] if empty else [choice.pk]) if multiple else choice.pk
            field.save()
            with self.assertNumQueries(1):
                metadata = CustomFieldSerializer(field).data
            self.assertEqual(field.default, metadata["default"])
            self.assertEqual([choice.pk], [item["id"] for item in metadata["choices"]])
            self.assertFalse(hasattr(field, "_prefetched_choices"))
