from datetime import date
from datetime import datetime
from datetime import timezone
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType

from app.custom_field.models import CustomField
from app.custom_field.models import CustomValue
from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.models import Person
from app.models import PersonType
from app.tests import APITestCase
from app.tests.factories import PersonFactory
from app.tests.factories import PersonTypeFactory


class CustomFieldBaseModelTest(APITestCase):
    # We use the app.Person model, which implements the CustomFieldBaseModel,
    # for testing because the CustomFieldBaseModel is abstract.

    def setUp(self) -> None:
        self.person_ct = ContentType.objects.get_for_model(Person)
        self.person_type: PersonType = PersonTypeFactory()
        self.person: Person = PersonFactory(person_type=self.person_type)

    def test_custom_field_base_model_custom_field_type_model(self) -> None:
        self.assertEqual(PersonType, Person.objects.get_type_model())

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
        choice_1: CustomValue = CustomValueFactory(
            field=field, label="Choice 1", value="choice_1"
        )

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
            {"id": choice_1.id, "label": "Choice 1", "value": "choice_1"},
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
            multiple=True,
        )
        choice_1: CustomValue = CustomValueFactory(field=field, value="2000-01-01")
        choice_2: CustomValue = CustomValueFactory(field=field, value="2001-01-01")
        choice_3: CustomValue = CustomValueFactory(field=field, value="2002-01-01")

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
                {"id": choice_1.id, "label": None, "value": "2000-01-01"},
                {"id": choice_2.id, "label": None, "value": "2001-01-01"},
                {"id": choice_3.id, "label": None, "value": "2002-01-01"},
            ],
            Person.objects.first().multiple_choice_value,
        )

    def test_custom_field_base_model_remove_text_value(self) -> None:
        CustomFieldFactory(
            identifier="text_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.TEXT,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.assertEqual(0, CustomValue.objects.count())

        self.person.text_value = "Text value"
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual("Text value", self.person.text_value)

        self.person.text_value = None
        self.person.save()

        self.assertEqual(0, CustomValue.objects.count())
        self.assertIsNone(self.person.text_value)

    def test_custom_field_base_model_remove_choice_value(self) -> None:
        field = CustomFieldFactory(
            identifier="choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
            choice_field=True,
        )

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        choice_1: CustomValue = CustomValueFactory(
            field=field, label="Choice 1", value="choice_1"
        )
        self.person.choice_value = choice_1
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(1, self.person.custom_values.count())
        self.assertEqual(choice_1, self.person.choice_value)

        self.person.choice_value = None
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, self.person.custom_values.count())
        self.assertIsNone(self.person.choice_value)

    def test_custom_field_base_model_remove_multiple_choice_value(
        self,
    ) -> None:
        field = CustomFieldFactory(
            identifier="multiple_choice_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.DATE,
            choice_field=True,
            multiple=True,
        )
        choice_1: CustomValue = CustomValueFactory(field=field, value="2000-01-01")
        CustomValueFactory(field=field, value="2001-01-01")
        choice_3: CustomValue = CustomValueFactory(field=field, value="2002-01-01")

        # we need to annotate the custom_field_keys manually or to fetch the person with the queryset again,
        # because we created a new field
        self.person.refresh_with_custom_fields()

        self.person.multiple_choice_value = [choice_1, choice_3]
        self.person.save()

        self.assertEqual(3, CustomValue.objects.count())
        self.assertEqual(2, self.person.custom_values.count())
        self.assertEqual(
            [
                {"id": choice_1.id, "label": None, "value": "2000-01-01"},
                {"id": choice_3.id, "label": None, "value": "2002-01-01"},
            ],
            Person.objects.first().multiple_choice_value,
        )

        self.person.multiple_choice_value = None
        self.person.save()

        self.assertEqual(3, CustomValue.objects.count())
        self.assertEqual(0, self.person.custom_values.count())
        self.assertIsNone(self.person.multiple_choice_value)

    def test_custom_field_base_model_set_value_with_set_custom_attr(self) -> None:
        CustomFieldFactory(
            identifier="char_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
        )

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.person.set_custom_attr("char_value", "Char value")

        self.assertEqual(0, CustomValue.objects.count())
        self.assertEqual(1, len(self.person._custom_values_to_save))
        self.person.save()

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(0, len(self.person._custom_values_to_save))

        self.assertEqual("Char value", self.person.char_value)
        self.assertEqual("Char value", Person.objects.first().char_value)
        self.assertEqual("Char value", CustomValue.objects.first().value)

    def test_custom_field_base_model_get_value_with_get_custom_attr(self) -> None:
        field: CustomField = CustomFieldFactory(
            identifier="char_value",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
        )
        self.person.custom_values.add(
            CustomValueFactory(field=field, value="Char value")
        )

        self.assertEqual(1, CustomValue.objects.count())
        self.assertEqual(1, self.person.custom_values.count())

        self.assertFalse(hasattr(self.person, "char_value"))
        self.assertEqual("Char value", self.person.get_custom_attr("char_value"))

    def test_type_change_invalidates_annotated_keys_without_a_query(self) -> None:
        second_type = PersonTypeFactory(title="Second type")
        CustomFieldFactory(
            identifier="first_value",
            content_type=self.person_ct,
            type_object=self.person_type,
        )
        CustomFieldFactory(
            identifier="second_value",
            content_type=self.person_ct,
            type_object=second_type,
        )

        relation_instance = Person.objects.get(pk=self.person.pk)
        self.assertEqual(["first_value"], relation_instance.custom_field_keys)
        with self.assertNumQueries(0):
            relation_instance.person_type = second_type
        self.assertNotIn("custom_field_keys", relation_instance.__dict__)

        attname_instance = Person.objects.get(pk=self.person.pk)
        self.assertEqual(["first_value"], attname_instance.custom_field_keys)
        with self.assertNumQueries(0):
            attname_instance.person_type_id = second_type.pk
        self.assertNotIn("custom_field_keys", attname_instance.__dict__)

    def test_unchanged_type_preserves_annotated_keys_without_a_query(self) -> None:
        CustomFieldFactory(
            identifier="type_value",
            content_type=self.person_ct,
            type_object=self.person_type,
        )

        relation_instance = Person.objects.get(pk=self.person.pk)
        relation_keys = relation_instance.custom_field_keys
        with self.assertNumQueries(0):
            relation_instance.person_type = self.person_type
        self.assertIs(relation_keys, relation_instance.custom_field_keys)

        attname_instance = Person.objects.get(pk=self.person.pk)
        attname_keys = attname_instance.custom_field_keys
        with self.assertNumQueries(0):
            attname_instance.person_type_id = self.person_type.pk
        self.assertIs(attname_keys, attname_instance.custom_field_keys)

    def test_type_null_transitions_invalidate_annotated_keys(self) -> None:
        CustomFieldFactory(
            identifier="typed_value",
            content_type=self.person_ct,
            type_object=self.person_type,
        )

        typed_person = Person.objects.get(pk=self.person.pk)
        with self.assertNumQueries(0):
            typed_person.person_type = None
        self.assertNotIn("custom_field_keys", typed_person.__dict__)

        untyped_person = PersonFactory(person_type=None)
        untyped_person = Person.objects.get(pk=untyped_person.pk)
        self.assertEqual([], untyped_person.custom_field_keys)
        with self.assertNumQueries(0):
            untyped_person.person_type_id = self.person_type.pk
        self.assertNotIn("custom_field_keys", untyped_person.__dict__)

    def test_deferred_type_assignment_invalidates_without_loading_type(self) -> None:
        CustomFieldFactory(
            identifier="typed_value",
            content_type=self.person_ct,
            type_object=self.person_type,
        )
        second_type = PersonTypeFactory(title="Second type")
        person = Person.objects.only("id").get(pk=self.person.pk)

        self.assertIn("custom_field_keys", person.__dict__)
        self.assertNotIn("person_type_id", person.__dict__)
        with self.assertNumQueries(0):
            person.person_type_id = second_type.pk
        self.assertNotIn("custom_field_keys", person.__dict__)

    def test_post_type_change_custom_write_refreshes_applicable_keys_once(
        self,
    ) -> None:
        first_field = CustomFieldFactory(
            identifier="first_value",
            content_type=self.person_ct,
            type_object=self.person_type,
        )
        second_type = PersonTypeFactory(title="Second type")
        second_field = CustomFieldFactory(
            identifier="second_value",
            content_type=self.person_ct,
            type_object=second_type,
        )
        global_field = CustomFieldFactory(
            identifier="global_value",
            content_type=self.person_ct,
        )
        person = Person.objects.get(pk=self.person.pk)
        person.set_custom_attr(first_field.identifier, "kept")
        person.save()

        person.person_type = second_type
        person.save(update_fields=["person_type"])
        self.assertNotIn("custom_field_keys", person.__dict__)

        with patch.object(
            person,
            "refresh_with_custom_fields",
            wraps=person.refresh_with_custom_fields,
        ) as refresh:
            person.set_custom_attr(second_field.identifier, "new")

        refresh.assert_called_once_with()
        self.assertEqual(
            [second_field.identifier, global_field.identifier],
            person.custom_field_keys,
        )
        self.assertEqual(1, len(person._custom_values_to_save))
        person.save()

        self.assertTrue(
            person.custom_values.filter(field=first_field, value="kept").exists()
        )
        self.assertTrue(
            person.custom_values.filter(field=second_field, value="new").exists()
        )

    def test_old_type_write_is_not_queued_after_type_change(self) -> None:
        first_field = CustomFieldFactory(
            identifier="first_value",
            content_type=self.person_ct,
            type_object=self.person_type,
        )
        second_type = PersonTypeFactory(title="Second type")
        CustomFieldFactory(
            identifier="second_value",
            content_type=self.person_ct,
            type_object=second_type,
        )
        person = Person.objects.get(pk=self.person.pk)
        person.set_custom_attr(first_field.identifier, "original")
        person.save()
        person.person_type = second_type
        person.save(update_fields=["person_type"])

        person.set_custom_attr(first_field.identifier, "ignored")

        self.assertEqual([], person._custom_values_to_save)
        person.save()
        self.assertTrue(
            person.custom_values.filter(
                field=first_field,
                value="original",
            ).exists()
        )
        self.assertFalse(
            person.custom_values.filter(
                field=first_field,
                value="ignored",
            ).exists()
        )
