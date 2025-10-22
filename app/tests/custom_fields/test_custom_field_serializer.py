from unittest.mock import ANY

from django.contrib.contenttypes.models import ContentType

from app.models import Person
from app.tests import APITestCase
from app.tests.custom_fields.factories import CustomFieldFactory
from app.tests.custom_fields.factories import CustomValueFactory
from django_features.custom_fields.models import CustomField
from django_features.custom_fields.serializers import CustomFieldSerializer


class CustomFieldViewSetTest(APITestCase):
    def test_custom_base_field_serializer(self) -> None:
        self.choice_field = CustomFieldFactory(
            identifier="custom_field_person",
            content_type=ContentType.objects.get_for_model(Person),
        )
        data = CustomFieldSerializer(self.choice_field).data
        self.assertDictEqual(
            {
                "choice_field": False,
                "choices": [],
                "created": ANY,
                "editable": True,
                "external_key": None,
                "field_type": "CHAR",
                "hidden": False,
                "id": 1,
                "identifier": "custom_field_person",
                "label": "Custom Field Label",
                "modified": ANY,
                "multiple": False,
                "order": 0,
            },
            data,
        )

    def test_custom_choice_field_serializer(self) -> None:
        self.choice_field = CustomFieldFactory(
            identifier="custom_field_person",
            choice_field=True,
            content_type=ContentType.objects.get_for_model(Person),
        )
        self.choice_1 = CustomValueFactory(
            field=self.choice_field,
            label="Choice 1",
            value="choice_1",
        )
        self.choice_2 = CustomValueFactory(
            field=self.choice_field,
            label="Choice 2",
            value="choice_2",
        )
        self.choice_3 = CustomValueFactory(
            field=self.choice_field,
            label="Choice 3",
            value="choice_3",
        )

        data = CustomFieldSerializer(self.choice_field).data
        self.assertDictEqual(
            {
                "choice_field": True,
                "choices": [
                    {
                        "id": self.choice_1.id,
                        "label": "Choice 1",
                        "value": "choice_1",
                    },
                    {
                        "id": self.choice_2.id,
                        "label": "Choice 2",
                        "value": "choice_2",
                    },
                    {
                        "id": self.choice_3.id,
                        "label": "Choice 3",
                        "value": "choice_3",
                    },
                ],
                "created": ANY,
                "editable": True,
                "external_key": None,
                "field_type": CustomField.FIELD_TYPES.CHAR,
                "hidden": False,
                "id": self.choice_field.id,
                "identifier": "custom_field_person",
                "label": "Custom Field Label",
                "modified": ANY,
                "multiple": False,
                "order": 0,
            },
            data,
        )
