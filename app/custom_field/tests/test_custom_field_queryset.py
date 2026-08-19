from django.contrib.contenttypes.models import ContentType

from app.custom_field.models import CustomField
from app.custom_field.tests.factories import CustomFieldFactory
from app.models import Municipality
from app.models import Person
from app.models import PersonType
from app.tests import APITestCase
from app.tests.factories import PersonTypeFactory


class CustomFieldQuerySetTest(APITestCase):
    def test_for_model_and_type_matches_the_type_content_type_and_id(self) -> None:
        person_type = PersonTypeFactory()
        default_field = CustomFieldFactory(identifier="default_value")
        typed_field = CustomFieldFactory(
            identifier="typed_value",
            type_content_type=ContentType.objects.get_for_model(PersonType),
            type_id=person_type.id,
        )
        wrong_content_type = CustomFieldFactory(
            identifier="coincidental_id",
            type_content_type=ContentType.objects.get_for_model(Municipality),
            type_id=person_type.id,
        )

        fields = CustomField.objects.for_model_and_type(
            Person, PersonType, person_type.id
        )

        self.assertSetEqual(set(fields), {default_field, typed_field})
        self.assertNotIn(wrong_content_type, fields)
