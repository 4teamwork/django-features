from datetime import date
from datetime import datetime
from datetime import timezone

from django.contrib.contenttypes.models import ContentType

from app.models import Person
from app.tests import APITestCase
from app.tests.custom_fields.factories import CustomFieldFactory
from app.tests.custom_fields.factories import CustomValueFactory
from app.tests.factories import PersonFactory
from django_features.custom_fields.models import CustomField
from django_features.custom_fields.models import CustomValue


class CustomFieldBaseModelTest(APITestCase):
    # We use the app.Person model, which implements the CustomFieldBaseModel,
    # for testing because the CustomFieldBaseModel is abstract.

    def setUp(self) -> None:
        self.person_ct = ContentType.objects.get_for_model(Person)
        self.person: Person = PersonFactory()  # type: ignore

    def test_custom_field_base_model_set_char_value(self) -> None:
        CustomFieldFactory(
            identifier="char_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.char_value = "Char value"
        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual("Char value", self.person.char_value)
        self.assertEqual("Char value", Person.objects.first().char_value)
        self.assertEqual("Char value", CustomValue.objects.first().value)

    def test_custom_field_base_model_set_text_value(self) -> None:
        CustomFieldFactory(
            identifier="text_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.TEXT,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.text_value = "Text value"
        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual("Text value", self.person.text_value)
        self.assertEqual("Text value", Person.objects.first().text_value)
        self.assertEqual("Text value", CustomValue.objects.first().value)

    def test_custom_field_base_model_set_date_value(self) -> None:
        CustomFieldFactory(
            identifier="date_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.date_value = date(1990, 5, 12)
        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual(date(1990, 5, 12), self.person.date_value)
        self.assertEqual(date(1990, 5, 12), Person.objects.first().date_value)
        self.assertEqual("1990-05-12", CustomValue.objects.first().value)

    def test_custom_field_base_model_set_datetime_value(self) -> None:
        CustomFieldFactory(
            identifier="datetime_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATETIME,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.datetime_value = datetime(1990, 5, 12, 12, 30, tzinfo=timezone.utc)
        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual(
            datetime(1990, 5, 12, 12, 30, tzinfo=timezone.utc),
            self.person.datetime_value,
        )
        self.assertEqual(
            datetime(1990, 5, 12, 12, 30, tzinfo=timezone.utc),
            Person.objects.first().datetime_value,
        )
        self.assertEqual("1990-05-12T14:30:00+02:00", CustomValue.objects.first().value)

    def test_custom_field_base_model_set_integer_value(self) -> None:
        CustomFieldFactory(
            identifier="integer_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.INTEGER,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.integer_value = 42
        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual(42, self.person.integer_value)
        self.assertEqual(42, Person.objects.first().integer_value)
        self.assertEqual(42, CustomValue.objects.first().value)

    def test_custom_field_base_model_set_boolean_value(self) -> None:
        CustomFieldFactory(
            identifier="boolean_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.BOOLEAN,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.boolean_value = True
        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual(True, self.person.boolean_value)
        self.assertEqual(True, Person.objects.first().boolean_value)
        self.assertEqual(True, CustomValue.objects.first().value)

    def test_custom_field_base_model_set_multiple_date_value(self) -> None:
        CustomFieldFactory(
            identifier="multiple_date_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            multiple=True,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.multiple_date_value = [
            date(2000, 1, 1),
            date(2001, 1, 1),
            date(2002, 1, 1),
        ]
        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertListEqual(
            [
                date(2000, 1, 1),
                date(2001, 1, 1),
                date(2002, 1, 1),
            ],
            self.person.multiple_date_value,
        )
        self.assertListEqual(
            [
                date(2000, 1, 1),
                date(2001, 1, 1),
                date(2002, 1, 1),
            ],
            Person.objects.first().multiple_date_value,
        )
        self.assertEqual(
            ["2000-01-01", "2001-01-01", "2002-01-01"],
            CustomValue.objects.first().value,
        )

    def test_custom_field_base_model_set_choice_value(self) -> None:
        field = CustomFieldFactory(
            identifier="choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
            choice_field=True,
        )
        choice_1 = CustomValueFactory(field=field, text="Choice 1", value="choice_1")

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.choice_value = choice_1
        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual(choice_1, self.person.choice_value)
        self.assertEqual(
            {"id": choice_1.id, "text": "Choice 1", "value": "choice_1"},
            Person.objects.first().choice_value,
        )

    def test_custom_field_base_model_set_multiple_choice_value(
        self,
    ) -> None:
        field = CustomFieldFactory(
            identifier="multiple_choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            choice_field=True,
            multiple_choice=True,
        )
        choice_1 = CustomValueFactory(field=field, value="2000-01-01")
        choice_2 = CustomValueFactory(field=field, value="2001-01-01")
        choice_3 = CustomValueFactory(field=field, value="2002-01-01")

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(3, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.multiple_choice_value = [choice_1, choice_2, choice_3]
        self.assertEqual(3, CustomValue.objects.count())
        self.assertEqual(3, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(3, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual(
            [choice_1, choice_2, choice_3], self.person.multiple_choice_value
        )
        self.assertEqual(
            [
                {"id": choice_1.id, "text": None, "value": "2000-01-01"},
                {"id": choice_2.id, "text": None, "value": "2001-01-01"},
                {"id": choice_3.id, "text": None, "value": "2002-01-01"},
            ],
            Person.objects.first().multiple_choice_value,
        )
