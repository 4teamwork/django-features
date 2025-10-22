from datetime import date
from datetime import datetime
from datetime import timezone

from django.contrib.contenttypes.models import ContentType

from app.models import Person
from app.models import PersonType
from app.tests import APITestCase
from app.tests.custom_fields.factories import CustomFieldFactory
from app.tests.custom_fields.factories import CustomValueFactory
from app.tests.factories import PersonFactory
from app.tests.factories import PersonTypeFactory
from django_features.custom_fields.models import CustomField


class CustomFieldBaseModelManagerTest(APITestCase):
    # We use the app.Person model, which implements the CustomFieldBaseModel,
    # for testing because the CustomFieldBaseModel is abstract.

    def setUp(self) -> None:
        self.person_ct = ContentType.objects.get_for_model(Person)
        self.person_type_1: PersonType = PersonTypeFactory()  # type: ignore
        self.person_type_2: PersonType = PersonTypeFactory()  # type: ignore
        self.person: Person = PersonFactory(person_type=self.person_type_1)  # type: ignore

    def test_custom_field_base_manager_annotate_custom_field_keys(self) -> None:
        CustomFieldFactory(identifier="birthday", content_type=self.person_ct)
        CustomFieldFactory(identifier="hobby", content_type=self.person_ct)
        self.assertEqual(
            ["birthday", "hobby"], Person.objects.first().custom_field_keys
        )

    def test_custom_field_base_manager_annotate_only_type_specific_fields(self) -> None:
        CustomFieldFactory(
            identifier="birthday",
            content_type=self.person_ct,
            type_object=self.person_type_1,
        )
        CustomFieldFactory(
            identifier="hobby",
            content_type=self.person_ct,
            type_object=self.person_type_2,
        )
        self.person.refresh_with_custom_fields()
        self.assertEqual(["birthday"], Person.objects.first().custom_field_keys)

    def test_custom_field_base_manager_annotate_char_value(self) -> None:
        field = CustomFieldFactory(
            identifier="char_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
        )
        value = CustomValueFactory(field=field, value="Some char value")
        self.person.custom_values.add(value)
        self.assertEqual("Some char value", Person.objects.first().char_value)

    def test_custom_field_base_manager_annotate_text_value(self) -> None:
        field = CustomFieldFactory(
            identifier="text_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.TEXT,
        )
        value = CustomValueFactory(field=field, value="Some text value")
        self.person.custom_values.add(value)
        self.assertEqual("Some text value", Person.objects.first().text_value)

    def test_custom_field_base_manager_annotate_date_value(self) -> None:
        field = CustomFieldFactory(
            identifier="date_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
        )
        value = CustomValueFactory(field=field, value="2000-01-01")
        self.person.custom_values.add(value)
        self.assertEqual(date(2000, 1, 1), Person.objects.first().date_value)

    def test_custom_field_base_manager_annotate_datetime_value(self) -> None:
        field = CustomFieldFactory(
            identifier="datetime_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATETIME,
        )
        value = CustomValueFactory(field=field, value="2000-01-01T12:30:00")
        self.person.custom_values.add(value)
        self.assertEqual(
            datetime(2000, 1, 1, 12, 30, tzinfo=timezone.utc),
            Person.objects.first().datetime_value,
        )

    def test_custom_field_base_manager_annotate_integer_value(self) -> None:
        field = CustomFieldFactory(
            identifier="integer_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.INTEGER,
        )
        value = CustomValueFactory(field=field, value=42)
        self.person.custom_values.add(value)
        self.assertEqual(42, Person.objects.first().integer_value)

    def test_custom_field_base_manager_annotate_boolean_value(self) -> None:
        field = CustomFieldFactory(
            identifier="boolean_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.BOOLEAN,
        )
        value = CustomValueFactory(field=field, value=True)
        self.person.custom_values.add(value)
        self.assertTrue(Person.objects.first().boolean_value)

    def test_custom_field_base_manager_annotate_multiple_date_value(self) -> None:
        field = CustomFieldFactory(
            identifier="multiple_date_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            multiple=True,
        )
        value = CustomValueFactory(
            field=field,
            value=["2000-1-1", "2001-1-1", "2002-1-1"],
        )
        self.person.custom_values.add(value)
        self.assertListEqual(
            [date(2000, 1, 1), date(2001, 1, 1), date(2002, 1, 1)],
            Person.objects.first().multiple_date_value,
        )

    def test_custom_field_base_manager_annotate_choice_value(self) -> None:
        field = CustomFieldFactory(
            identifier="choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            choice_field=True,
        )
        choice_1 = CustomValueFactory(field=field, text_de="Choice 1", value="choice_1")
        self.person.custom_values.add(choice_1)
        self.assertEqual(
            {"id": choice_1.id, "text": "Choice 1", "value": "choice_1"},
            Person.objects.first().choice_value,
        )

    def test_custom_field_base_manager_annotate_multiple_date_choice_value(
        self,
    ) -> None:
        field = CustomFieldFactory(
            identifier="multiple_choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            choice_field=True,
            multiple=True,
        )
        choice_1 = CustomValueFactory(
            field=field, text_de="Choice 1", value="2000-01-01"
        )
        choice_2 = CustomValueFactory(
            field=field, text_de="Choice 2", value="2001-01-01"
        )
        choice_3 = CustomValueFactory(
            field=field, text_de="Choice 3", value="2002-01-01"
        )
        self.person.custom_values.set([choice_1, choice_2, choice_3])
        self.assertEqual(
            [
                {"id": choice_1.id, "text": "Choice 1", "value": "2000-01-01"},
                {"id": choice_2.id, "text": "Choice 2", "value": "2001-01-01"},
                {"id": choice_3.id, "text": "Choice 3", "value": "2002-01-01"},
            ],
            Person.objects.first().multiple_choice_value,
        )
