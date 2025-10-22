from datetime import date
from datetime import datetime
from datetime import timezone

from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import ValidationError

from app.models import Person
from app.serializers.person import PersonSerializer
from app.tests import APITestCase
from app.tests.custom_fields.factories import CustomFieldFactory
from app.tests.custom_fields.factories import CustomValueFactory
from app.tests.factories import PersonFactory
from django_features.custom_fields.models import CustomField
from django_features.custom_fields.models import CustomValue


class CustomFieldBaseModelSerializerTest(APITestCase):
    # We use the app.Person model, which implements the CustomFieldBaseModel,
    # for testing because the CustomFieldBaseModel is abstract.

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
            multiple=True,
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

        self.person: Person = PersonFactory()  # type: ignore
        self.person.refresh_with_custom_fields()

    def test_custom_field_base_model_serializer_data(self) -> None:
        self.person.char_value = "Some char value"
        self.person.text_value = "Some text value"
        self.person.date_value = date(2000, 1, 1)
        self.person.datetime_value = datetime(2000, 1, 1, 12, 30)
        self.person.integer_value = 42
        self.person.boolean_value = True
        self.person.boolean_value = True
        self.person.multiple_date_value = [date(2000, 1, 1), date(2001, 1, 1)]
        self.person.choice_value = self.choice_1
        self.person.multiple_choice_value = [
            self.multiple_choice_1,
            self.multiple_choice_2,
        ]
        self.person.save()

        data = PersonSerializer(self.person).data
        self.assertDictEqual(
            {
                "email": "john.doe@example.com",
                "firstname": "John",
                "lastname": "Doe",
                "char_value": "Some char value",
                "text_value": "Some text value",
                "date_value": "2000-01-01",
                "datetime_value": "2000-01-01T12:30:00+01:00",
                "integer_value": 42,
                "boolean_value": True,
                "multiple_date_value": ["2000-01-01", "2001-01-01"],
                "choice_value": {
                    "id": self.choice_1.id,
                    "label": None,
                    "value": "2000-01-01",
                },
                "multiple_choice_value": [
                    {
                        "id": self.multiple_choice_1.id,
                        "label": None,
                        "value": "2000-01-01",
                    },
                    {
                        "id": self.multiple_choice_2.id,
                        "label": None,
                        "value": "2001-01-01",
                    },
                ],
            },
            data,
        )

    def test_custom_field_base_model_serializer_create(self) -> None:
        data = {
            "email": "john.doe@example.com",
            "firstname": "John",
            "lastname": "Doe",
            "char_value": "Some char value",
            "text_value": "Some text value",
            "date_value": "2000-01-01",
            "datetime_value": "2000-01-01T12:30:00+01:00",
            "integer_value": 42,
            "boolean_value": True,
            "multiple_date_value": ["2000-01-01", "2001-01-01"],
            "choice_value": self.choice_1.id,
            "multiple_choice_value": [
                self.multiple_choice_1.id,
                self.multiple_choice_2.id,
            ],
        }
        serializer = PersonSerializer(data=data)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        instance = serializer.save()

        instance.refresh_with_custom_fields()

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
            {"id": self.choice_1.id, "label": None, "value": "2000-01-01"},
        )
        self.assertEqual(
            instance.multiple_choice_value,
            [
                {"id": self.multiple_choice_1.id, "label": None, "value": "2000-01-01"},
                {"id": self.multiple_choice_2.id, "label": None, "value": "2001-01-01"},
            ],
        )

    def test_custom_field_base_model_serializer_update(self) -> None:
        self.person.char_value = "Some char value"
        self.person.text_value = "Some text value"
        self.person.date_value = date(2000, 1, 1)
        self.person.datetime_value = datetime(2000, 1, 1, 12, 30)
        self.person.integer_value = 42
        self.person.boolean_value = True
        self.person.multiple_date_value = [date(2000, 1, 1), date(2001, 1, 1)]
        self.person.choice_value = self.choice_1
        self.person.multiple_choice_value = [
            self.multiple_choice_1,
            self.multiple_choice_2,
        ]
        self.person.save()

        data = PersonSerializer(self.person).data
        self.assertDictEqual(
            {
                "email": "john.doe@example.com",
                "firstname": "John",
                "lastname": "Doe",
                "char_value": "Some char value",
                "text_value": "Some text value",
                "date_value": "2000-01-01",
                "datetime_value": "2000-01-01T12:30:00+01:00",
                "integer_value": 42,
                "boolean_value": True,
                "multiple_date_value": ["2000-01-01", "2001-01-01"],
                "choice_value": {
                    "id": self.choice_1.id,
                    "label": None,
                    "value": "2000-01-01",
                },
                "multiple_choice_value": [
                    {
                        "id": self.multiple_choice_1.id,
                        "label": None,
                        "value": "2000-01-01",
                    },
                    {
                        "id": self.multiple_choice_2.id,
                        "label": None,
                        "value": "2001-01-01",
                    },
                ],
            },
            data,
        )

        data = {
            "email": "john.doe2@example.com",
            "firstname": "John2",
            "lastname": "Doe2",
            "char_value": "Some char value2",
            "text_value": "Some text value2",
            "date_value": "2000-01-02",
            "datetime_value": "2000-01-02T12:30:00+01:00",
            "integer_value": 43,
            "boolean_value": False,
            "multiple_date_value": ["2002-01-01", "2003-01-01"],
            "choice_value": {
                "id": self.choice_2.id,
                "label": None,
                "value": "2000-01-01",
            },
            "multiple_choice_value": [
                {
                    "id": self.multiple_choice_1.id,
                    "label": None,
                    "value": "2000-01-01",
                },
                {
                    "id": self.multiple_choice_3.id,
                    "label": None,
                    "value": "2002-01-01",
                },
            ],
        }

        serializer = PersonSerializer(self.person, data=data)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()
        instance.refresh_with_custom_fields()

        self.assertEqual(instance.firstname, "John2")
        self.assertEqual(instance.lastname, "Doe2")
        self.assertEqual(instance.email, "john.doe2@example.com")
        self.assertEqual(instance.char_value, "Some char value2")
        self.assertEqual(instance.text_value, "Some text value2")
        self.assertEqual(instance.date_value, date(2000, 1, 2))
        self.assertEqual(
            instance.datetime_value, datetime(2000, 1, 2, 11, 30, tzinfo=timezone.utc)
        )
        self.assertEqual(instance.integer_value, 43)
        self.assertEqual(instance.boolean_value, False)
        self.assertEqual(
            instance.multiple_date_value, [date(2002, 1, 1), date(2003, 1, 1)]
        )
        self.assertEqual(
            instance.choice_value,
            {"id": self.choice_2.id, "label": None, "value": "2001-01-01"},
        )
        self.assertEqual(
            instance.multiple_choice_value,
            [
                {"id": self.multiple_choice_1.id, "label": None, "value": "2000-01-01"},
                {"id": self.multiple_choice_3.id, "label": None, "value": "2002-01-01"},
            ],
        )

    def test_custom_field_base_model_serializer_partial_update(self) -> None:
        self.person.char_value = "Some char value"
        self.person.text_value = "Some text value"
        self.person.date_value = date(2000, 1, 1)
        self.person.datetime_value = datetime(2000, 1, 1, 12, 30)
        self.person.integer_value = 42
        self.person.boolean_value = True
        self.person.multiple_date_value = [date(2000, 1, 1), date(2001, 1, 1)]
        self.person.choice_value = self.choice_1
        self.person.multiple_choice_value = [
            self.multiple_choice_1,
            self.multiple_choice_2,
        ]
        self.person.save()

        data = PersonSerializer(self.person).data
        self.assertDictEqual(
            {
                "email": "john.doe@example.com",
                "firstname": "John",
                "lastname": "Doe",
                "char_value": "Some char value",
                "text_value": "Some text value",
                "date_value": "2000-01-01",
                "datetime_value": "2000-01-01T12:30:00+01:00",
                "integer_value": 42,
                "boolean_value": True,
                "multiple_date_value": ["2000-01-01", "2001-01-01"],
                "choice_value": {
                    "id": self.choice_1.id,
                    "label": None,
                    "value": "2000-01-01",
                },
                "multiple_choice_value": [
                    {
                        "id": self.multiple_choice_1.id,
                        "label": None,
                        "value": "2000-01-01",
                    },
                    {
                        "id": self.multiple_choice_2.id,
                        "label": None,
                        "value": "2001-01-01",
                    },
                ],
            },
            data,
        )

        data = {
            "char_value": "Some char value2",
            "datetime_value": "2000-01-02T12:30:00+01:00",
            "integer_value": 43,
            "multiple_choice_value": [],
        }

        serializer = PersonSerializer(self.person, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        instance.refresh_with_custom_fields()

        self.assertEqual(instance.char_value, "Some char value2")
        self.assertEqual(instance.text_value, "Some text value")
        self.assertEqual(instance.date_value, date(2000, 1, 1))
        self.assertEqual(
            instance.datetime_value, datetime(2000, 1, 2, 11, 30, tzinfo=timezone.utc)
        )
        self.assertEqual(instance.integer_value, 43)
        self.assertEqual(instance.boolean_value, True)
        self.assertEqual(
            instance.multiple_date_value, [date(2000, 1, 1), date(2001, 1, 1)]
        )
        self.assertEqual(
            instance.choice_value,
            {"id": self.choice_1.id, "label": None, "value": "2000-01-01"},
        )
        self.assertEqual(instance.multiple_choice_value, [])

    def test_custom_field_base_model_serializer_required_field(self) -> None:
        CustomFieldFactory(
            identifier="required_field",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
            required=True,
        )

        data = {
            "email": "john.doe@example.com",
            "firstname": "John",
            "lastname": "Doe",
        }

        serializer = PersonSerializer(data=data)
        with self.assertRaises(ValidationError) as e:
            serializer.is_valid(raise_exception=True)
        self.assertEqual(
            e.exception.detail,
            {"required_field": ["Dieses Feld ist zwingend erforderlich."]},
        )

    def test_custom_field_base_model_serializer_blank_not_allowed(self) -> None:
        CustomFieldFactory(
            identifier="not_blank",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
            allow_blank=False,
        )

        data = {
            "email": "john.doe@example.com",
            "firstname": "John",
            "lastname": "Doe",
            "not_blank": "",
        }

        serializer = PersonSerializer(data=data)
        with self.assertRaises(ValidationError) as e:
            serializer.is_valid(raise_exception=True)
        self.assertEqual(
            e.exception.detail,
            {"not_blank": ["Dieses Feld darf nicht leer sein."]},
        )

    def test_custom_field_base_model_serializer_null_not_allowed(self) -> None:
        CustomFieldFactory(
            identifier="not_null",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
            allow_null=False,
        )

        data = {
            "email": "john.doe@example.com",
            "firstname": "John",
            "lastname": "Doe",
            "not_null": None,
        }

        serializer = PersonSerializer(data=data)
        with self.assertRaises(ValidationError) as e:
            serializer.is_valid(raise_exception=True)
        self.assertEqual(
            e.exception.detail,
            {"not_null": ["Dieses Feld darf nicht null sein."]},
        )

    def test_custom_field_base_model_serializer_default_value(self) -> None:
        CustomFieldFactory(
            identifier="default_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            default="2000-01-01",
        )
        CustomFieldFactory(
            identifier="no_default_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
        )

        data = {
            "email": "john.doe@example.com",
            "firstname": "John",
            "lastname": "Doe",
        }

        serializer = PersonSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        instance.refresh_with_custom_fields()

        self.assertEqual(instance.default_value, date(2000, 1, 1))
        self.assertEqual(instance.no_default_value, None)

        self.assertEqual(
            1, CustomValue.objects.filter(field__choice_field=False).count()
        )
