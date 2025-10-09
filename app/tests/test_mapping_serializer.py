from datetime import date
from datetime import datetime
from datetime import timezone

from constance.test import override_config
from django.contrib.contenttypes.models import ContentType

from app.models import Municipality
from app.models import Person
from app.serializers.person import PersonMappingSerializer
from app.tests import APITestCase
from app.tests.custom_fields.factories import CustomFieldFactory
from app.tests.custom_fields.factories import CustomValueFactory
from app.tests.factories import AddressFactory
from app.tests.factories import PersonFactory
from django_features.custom_fields.models import CustomField


MODEL_MAPPING_FIELD = {
    "person": {
        "external_firstname": "firstname",
        "external_lastname": "lastname",
        "external_char_field": "char_value",
        "external_text_field": "text_value",
        "external_date_field": "date_value",
        "external_datetime_field": "datetime_value",
        "external_integer_field": "integer_value",
        "external_boolean_field": "boolean_value",
        "external_multiple_date_field": "multiple_date_value",
        "external_choice_field": "choice_value",
        "external_multiple_choice_field": "multiple_choice_value",
        "external_municipality_title": "place_of_residence.title",
        "external_addresses": "addresses",
    }
}


class MappingSerializerTestCase(APITestCase):
    # We use the app.Person mapping serializer, which implements the MappingSerializer,
    # for testing because the MappingSerializer is abstract.

    def setUp(self) -> None:
        self.person_ct = ContentType.objects.get_for_model(Person)

        self.char_field = CustomFieldFactory(
            identifier="char_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
        )
        self.text_field = CustomFieldFactory(
            identifier="text_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.TEXT,
        )
        self.date_field = CustomFieldFactory(
            identifier="date_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
        )
        self.datetime_field = CustomFieldFactory(
            identifier="datetime_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATETIME,
        )
        self.integer_field = CustomFieldFactory(
            identifier="integer_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.INTEGER,
        )
        self.boolean_field = CustomFieldFactory(
            identifier="boolean_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.BOOLEAN,
        )
        self.multiple_date_field = CustomFieldFactory(
            identifier="multiple_date_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            multiple=True,
        )
        self.choice_field = CustomFieldFactory(
            identifier="choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            choice_field=True,
        )
        self.multiple_choice_field = CustomFieldFactory(
            identifier="multiple_choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            choice_field=True,
            multiple_choice=True,
        )

        self.choice_1 = CustomValueFactory(field=self.choice_field, value="2000-01-01")
        self.choice_2 = CustomValueFactory(field=self.choice_field, value="2001-01-01")

        self.multiple_choice_1 = CustomValueFactory(
            field=self.multiple_choice_field, value="2000-01-01"
        )
        self.multiple_choice_2 = CustomValueFactory(
            field=self.multiple_choice_field, value="2001-01-01"
        )
        self.multiple_choice_3 = CustomValueFactory(
            field=self.multiple_choice_field, value="2002-01-01"
        )

        self.address_1 = AddressFactory()
        self.address_2 = AddressFactory()
        self.address_3 = AddressFactory()

    @override_config(MODEL_MAPPING_FIELD=MODEL_MAPPING_FIELD)
    def test_mapping_serializer_create(self) -> None:
        data = {
            "external_firstname": "Hugo",
            "external_lastname": "Boss",
            "external_char_field": "Some char value",
            "external_text_field": "Some text value",
            "external_date_field": "2000-01-01",
            "external_datetime_field": "2000-01-01T12:30:00+01:00",
            "external_integer_field": 42,
            "external_boolean_field": True,
            "external_multiple_date_field": ["2000-01-01", "2001-01-01"],
            "external_choice_field": "2000-01-01",
            "external_multiple_choice_field": ["2000-01-01", "2001-01-01"],
            "external_municipality_title": "Muri",
            "external_addresses": [
                self.address_1.external_uid,
                self.address_2.external_uid,
            ],
        }

        serializer = PersonMappingSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save()

        instance.refresh_with_custom_fields()

        self.assertEqual("Hugo", instance.firstname)
        self.assertEqual("Boss", instance.lastname)

        self.assertEqual(instance.char_value, "Some char value")
        self.assertEqual(instance.text_value, "Some text value")
        self.assertEqual(instance.date_value, date(2000, 1, 1))
        self.assertEqual(
            instance.datetime_value, datetime(2000, 1, 1, 11, 30, tzinfo=timezone.utc)
        )
        self.assertEqual(instance.integer_value, 42)
        self.assertEqual(instance.boolean_value, True)
        self.assertEqual(
            instance.multiple_date_value, [date(2000, 1, 1), date(2001, 1, 1)]
        )
        self.assertEqual(
            instance.choice_value,
            {"id": self.choice_1.id, "text": None, "value": "2000-01-01"},
        )
        self.assertEqual(
            instance.multiple_choice_value,
            [
                {"id": self.multiple_choice_1.id, "text": None, "value": "2000-01-01"},
                {"id": self.multiple_choice_2.id, "text": None, "value": "2001-01-01"},
            ],
        )

        self.assertEqual("Muri", instance.place_of_residence.title)
        self.assertEqual(1, Municipality.objects.count())
        self.assertEqual(2, instance.addresses.count())
        self.assertEqual(instance, instance.addresses.first().target)
        self.assertEqual(instance, instance.addresses.last().target)

    @override_config(MODEL_MAPPING_FIELD=MODEL_MAPPING_FIELD)
    def test_mapping_serializer_update(self) -> None:
        person: Person = PersonFactory(firstname="old", lastname="old")  # type: ignore

        person.refresh_with_custom_fields()

        data = {
            "external_firstname": "Hugo2",
            "external_lastname": "Boss2",
            "external_char_field": "Some char value2",
            "external_text_field": "Some text value2",
            "external_date_field": "2000-01-02",
            "external_datetime_field": "2000-01-02T12:30:00+01:00",
            "external_integer_field": 43,
            "external_boolean_field": False,
            "external_multiple_date_field": ["2000-01-01", "2001-02-01"],
            "external_choice_field": "2001-01-01",
            "external_multiple_choice_field": ["2000-01-01", "2002-01-01"],
            "external_municipality_title": "Koeniz",
            "external_addresses": [
                self.address_1.external_uid,
                self.address_3.external_uid,
            ],
        }

        serializer = PersonMappingSerializer(person, data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save()

        instance.refresh_with_custom_fields()

        self.assertEqual("Hugo2", instance.firstname)
        self.assertEqual("Boss2", instance.lastname)

        self.assertEqual(instance.char_value, "Some char value2")
        self.assertEqual(instance.text_value, "Some text value2")
        self.assertEqual(instance.date_value, date(2000, 1, 2))
        self.assertEqual(
            instance.datetime_value, datetime(2000, 1, 2, 11, 30, tzinfo=timezone.utc)
        )
        self.assertEqual(instance.integer_value, 43)
        self.assertEqual(instance.boolean_value, False)
        self.assertEqual(
            instance.multiple_date_value, [date(2000, 1, 1), date(2001, 2, 1)]
        )
        self.assertEqual(
            instance.choice_value,
            {"id": self.choice_2.id, "text": None, "value": "2001-01-01"},
        )
        self.assertEqual(
            instance.multiple_choice_value,
            [
                {"id": self.multiple_choice_1.id, "text": None, "value": "2000-01-01"},
                {"id": self.multiple_choice_3.id, "text": None, "value": "2002-01-01"},
            ],
        )

        self.assertEqual("Koeniz", instance.place_of_residence.title)
        self.assertEqual(1, Municipality.objects.count())
        self.assertEqual(2, instance.addresses.count())
        self.assertEqual(person, instance.addresses.first().target)
        self.assertEqual(person, instance.addresses.last().target)
