from unittest.mock import patch

from rest_framework import serializers

from app.custom_field.models import CustomField
from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.custom_field.tests.serializers import TrustedPersonSerializer
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.tests import APITestCase
from app.tests.factories import PersonFactory


class CustomFieldEditabilityTest(APITestCase):
    def setUp(self) -> None:
        self.field = CustomFieldFactory(identifier="protected", editable=False)

    def test_omitted_noneditable_field_is_permitted(self) -> None:
        serializer = TypeAwarePersonSerializer(data={"firstname": "Omitted"})

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_omitted_required_noneditable_field_is_permitted(self) -> None:
        self.field.required = True
        self.field.save(update_fields=["required"])
        serializer = TypeAwarePersonSerializer(data={"firstname": "Omitted"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()
        self.assertFalse(person.custom_values.filter(field=self.field).exists())

    def test_create_applies_default_for_noneditable_field(self) -> None:
        self.field.default = "default value"
        self.field.save(update_fields=["default"])
        serializer = TypeAwarePersonSerializer(data={"firstname": "Created"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(
            person.custom_values.get(field=self.field).value,
            "default value",
        )

    def test_create_applies_default_for_required_noneditable_field(self) -> None:
        self.field.default = "default value"
        self.field.required = True
        self.field.save(update_fields=["default", "required"])
        serializer = TypeAwarePersonSerializer(data={"firstname": "Created"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(
            person.custom_values.get(field=self.field).value,
            "default value",
        )

    def test_explicit_noneditable_field_is_rejected(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data={"firstname": "Manual", self.field.identifier: "client value"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn(self.field.identifier, serializer.errors)

    def test_update_rejects_same_and_changed_noneditable_values(self) -> None:
        person = PersonFactory(firstname="Before")
        person.custom_values.create(field=self.field, value="managed value")

        for submitted in ("managed value", "changed value"):
            with self.subTest(submitted=submitted):
                serializer = TypeAwarePersonSerializer(
                    person,
                    data={
                        "firstname": "After",
                        self.field.identifier: submitted,
                    },
                    partial=True,
                )

                self.assertFalse(serializer.is_valid())
                self.assertEqual(
                    serializer.errors[self.field.identifier][0].code,
                    "invalid",
                )
                self.assertTrue(str(serializer.errors[self.field.identifier][0]))

                person.refresh_from_db()
                self.assertEqual(person.firstname, "Before")
                self.assertEqual(
                    person.custom_values.get(field=self.field).value,
                    "managed value",
                )

    def test_partial_update_preserves_omitted_noneditable_value(self) -> None:
        person = PersonFactory(firstname="Before")
        person.custom_values.create(field=self.field, value="managed value")
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(
            person.custom_values.get(field=self.field).value,
            "managed value",
        )

    def test_partial_update_preserves_omitted_protected_choices(self) -> None:
        single_field = CustomFieldFactory(
            identifier="protected_single_choice",
            choice_field=True,
            editable=False,
        )
        single_choice = CustomValueFactory(field=single_field)
        multiple_field = CustomFieldFactory(
            identifier="protected_multiple_choices",
            choice_field=True,
            editable=False,
            multiple=True,
        )
        multiple_choices = [
            CustomValueFactory(field=multiple_field),
            CustomValueFactory(field=multiple_field),
        ]
        person = PersonFactory(firstname="Before")
        person.custom_values.add(single_choice, *multiple_choices)
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertSetEqual(
            set(person.custom_values.values_list("pk", flat=True)),
            {single_choice.pk, *(choice.pk for choice in multiple_choices)},
        )

    def test_writability_hook_can_allow_trusted_values(self) -> None:
        serializer = TrustedPersonSerializer(
            data={"firstname": "Trusted", self.field.identifier: "server value"},
            context={"trusted_fields": {self.field.identifier}},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()
        self.assertEqual(
            person.custom_values.get(field=self.field).value, "server value"
        )

    def test_writability_hook_can_update_trusted_values(self) -> None:
        person = PersonFactory()
        person.custom_values.create(field=self.field, value="before")
        serializer = TrustedPersonSerializer(
            person,
            data={self.field.identifier: "after"},
            partial=True,
            context={"trusted_fields": {self.field.identifier}},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(person.custom_values.get(field=self.field).value, "after")

    def test_writability_hook_keeps_required_validation(self) -> None:
        self.field.required = True
        self.field.save(update_fields=["required"])
        serializer = TrustedPersonSerializer(
            data={"firstname": "Trusted"},
            context={"trusted_fields": {self.field.identifier}},
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors[self.field.identifier][0].code,
            "required",
        )

    def test_full_update_preserves_omitted_noneditable_value_with_default(
        self,
    ) -> None:
        self.field.default = "default value"
        self.field.save(update_fields=["default"])
        person = PersonFactory(firstname="Before")
        person.custom_values.create(field=self.field, value="managed value")
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After", "lastname": person.lastname},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(
            person.custom_values.get(field=self.field).value,
            "managed value",
        )

    def test_full_update_preserves_omitted_required_noneditable_value(self) -> None:
        self.field.required = True
        self.field.save(update_fields=["required"])
        person = PersonFactory(firstname="Before")
        person.custom_values.create(field=self.field, value="managed value")
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After", "lastname": person.lastname},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(
            person.custom_values.get(field=self.field).value,
            "managed value",
        )

    def test_full_update_does_not_create_omitted_noneditable_default(self) -> None:
        self.field.default = "default value"
        self.field.save(update_fields=["default"])
        person = PersonFactory(firstname="Before")
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After", "lastname": person.lastname},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertFalse(person.custom_values.filter(field=self.field).exists())

    def test_full_update_preserves_omitted_editable_value_with_default(self) -> None:
        self.field.editable = True
        self.field.default = "default value"
        self.field.save(update_fields=["default", "editable"])
        person = PersonFactory(firstname="Before")
        person.custom_values.create(field=self.field, value="existing value")
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After", "lastname": person.lastname},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(
            person.custom_values.get(field=self.field).value,
            "existing value",
        )

    def test_full_update_does_not_create_omitted_editable_default(self) -> None:
        self.field.editable = True
        self.field.default = "default value"
        self.field.save(update_fields=["default", "editable"])
        person = PersonFactory(firstname="Before")
        serializer = TypeAwarePersonSerializer(
            person,
            data={"firstname": "After", "lastname": person.lastname},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertFalse(person.custom_values.filter(field=self.field).exists())

    def test_update_runs_custom_field_validators_once(self) -> None:
        calls: list[str] = []

        class CountingCharField(serializers.CharField):
            def run_validators(self, value: str) -> None:
                calls.append(value)
                super().run_validators(value)

        self.field.editable = True
        self.field.save(update_fields=["editable"])
        person = PersonFactory()
        with patch.dict(
            CustomField.TYPE_SERIALIZER_MAP,
            {CustomField.FIELD_TYPES.CHAR: CountingCharField},
        ):
            serializer = TypeAwarePersonSerializer(
                person,
                data={self.field.identifier: "updated"},
                partial=True,
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            serializer.save()

        self.assertEqual(calls, ["updated"])
