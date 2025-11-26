from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from app.models import Address
from app.models import Person
from app.tests import APITestCase
from django_features.custom_fields.factories import CustomFieldFactory
from django_features.custom_fields.models import CustomField
from django_features.settings.fields import ModelFieldMapping


class ModelFieldMappingTestCase(APITestCase):
    def setUp(self) -> None:
        self.person_ct = ContentType.objects.get_for_model(Person)
        self.address_ct = ContentType.objects.get_for_model(Address)
        CustomFieldFactory(  # type: ignore
            identifier="person_custom_field",
            content_type=self.person_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
        )
        CustomFieldFactory(  # type: ignore
            identifier="address_custom_field",
            content_type=self.address_ct,
            field_type=CustomField.FIELD_TYPES.CHAR,
        )

    def test_validate_default_mapping_validation(self) -> None:
        validator = ModelFieldMapping()

        mapping = {
            "unique_choice_field": "custom_unique_choice_field",
            "person": {
                "external_firstname": "firstname",
                "external_lastname": "lastname",
                "external_custom_field": "person_custom_field",
                "external_addresses": "addresses",
                "external_municipality_title": "place_of_residence.title",
            },
            "address": {
                "external_city": "city",
                "external_country": "country",
                "external_street": "street",
                "external_uid": "external_uid",
                "external_zip_code": "zip_code",
                "external_custom_field": "address_custom_field",
            },
        }

        validator.validate(mapping)

    def test_invalid_required_field(self) -> None:
        validator = ModelFieldMapping()

        mapping = {
            "person": {
                "external_lastname": "lastname",
            },
        }

        with self.assertRaises(ValidationError) as e:
            validator.validate(mapping)

        self.assertEqual(
            "Required field 'firstname' not found in field mapping.",
            e.exception.message,
        )

    def test_do_not_validate_required_fields(self) -> None:
        validator = ModelFieldMapping(validate_required=False)

        mapping = {
            "person": {
                "external_lastname": "lastname",
            },
        }

        validator.validate(mapping)

    def test_invalid_nested_generic_field(self) -> None:
        validator = ModelFieldMapping()

        mapping = {
            "person": {
                "external_firstname": "firstname",
                "external_addresses.city": "addresses.city",
            },
        }

        with self.assertRaises(ValidationError) as e:
            validator.validate(mapping)

        self.assertEqual(
            "Field 'app.Person.addresses' is a generic relation and cannot be nested.",
            e.exception.message,
        )

    def test_do_not_allow_relations(self) -> None:
        validator = ModelFieldMapping(allow_relations=False)

        mapping = {
            "person": {
                "external_firstname": "firstname",
                "external_addresses.city": "addresses.city",
            },
        }

        with self.assertRaises(ValidationError) as e:
            validator.validate(mapping)

        self.assertEqual(
            "Field 'app.Person.addresses' is a relation and cannot be assigned.",
            e.exception.message,
        )

    def test_invalid_value_field(self) -> None:
        validator = ModelFieldMapping(allow_relations=False)

        mapping = {
            "person": {
                "external_firstname": "firstname",
                "external_field": "field",
            },
        }

        with self.assertRaises(ValidationError) as e:
            validator.validate(mapping)

        self.assertEqual(
            "Invalid field 'field' for model <class 'app.models.person.Person'>.",
            e.exception.message,
        )

    def test_relation_separator(self) -> None:
        validator = ModelFieldMapping(relation_separator="__")

        mapping = {
            "person": {
                "external_firstname": "firstname",
                "external_municipality_title": "place_of_residence__title",
            },
        }

        validator.validate(mapping)

    def test_do_not_validate_custom_fields(self) -> None:
        validator = ModelFieldMapping(validate_custom_fields=False)

        mapping = {
            "person": {
                "external_firstname": "firstname",
                "external_custom_field": "person_custom_field",
            },
        }

        with self.assertRaises(ValidationError) as e:
            validator.validate(mapping)

        self.assertEqual(
            "Invalid field 'person_custom_field' for model <class 'app.models.person.Person'>.",
            e.exception.message,
        )

    def test_validate_key_instead_of_value(self) -> None:
        validator = ModelFieldMapping(validate_key=True, validate_value=False)

        mapping = {
            "person": {
                "firstname": "Name",
            },
        }

        validator.validate(mapping)

    def test_invalid_key_field(self) -> None:
        validator = ModelFieldMapping(validate_key=True, validate_value=False)

        mapping = {
            "person": {
                "firstname": "Name",
                "field": "Field",
            },
        }

        with self.assertRaises(ValidationError) as e:
            validator.validate(mapping)

        self.assertEqual(
            "Invalid field 'field' for model <class 'app.models.person.Person'>.",
            e.exception.message,
        )
