import random
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand

from app.models import Person
from django_features.custom_fields.models import CustomField
from django_features.custom_fields.models import CustomValue


class Command(BaseCommand):
    NUMBER_OF_CUSTOM_FIELDS = 100
    NUMBER_OF_OBJECTS = 1000

    def _value_for_type(self, field_type: str) -> Any:
        match field_type:
            case CustomField.FIELD_TYPES.CHAR:
                return "custom char field"
            case CustomField.FIELD_TYPES.TEXT:
                return "custom text field\nsecond line"
            case CustomField.FIELD_TYPES.INTEGER:
                return 123456789
            case CustomField.FIELD_TYPES.DATE:
                return "2025-01-01"
            case CustomField.FIELD_TYPES.DATETIME:
                return "2025-01-01T00:00:00Z"
            case CustomField.FIELD_TYPES.BOOLEAN:
                return random.choice([True, False])

    def handle(self, *args: Any, **options: Any) -> None:
        custom_fields = []
        custom_values = []
        objects = []

        field_type = 0
        person_c = ContentType.objects.get_for_model(Person)
        print("Add objects")
        for i in range(self.NUMBER_OF_OBJECTS):
            objects.append(Person(firstname=f"Firstname {i}", lastname=f"Lastname {i}"))

        print("Add custom fields")
        for i in range(self.NUMBER_OF_CUSTOM_FIELDS):
            custom_fields.append(
                CustomField(
                    content_type=person_c,
                    field_type=CustomField.TYPE_CHOICES[field_type][0],
                    identifier=f"custom_field_{i}",
                    label=f"Custom field {i}",
                )
            )
            field_type = (
                field_type + 1 if field_type < len(CustomField.TYPE_CHOICES) - 1 else 0
            )

        print("Add custom values")
        for i in range(self.NUMBER_OF_OBJECTS):
            for c in range(self.NUMBER_OF_CUSTOM_FIELDS):
                field = custom_fields[c]
                custom_values.append(
                    CustomValue(
                        field=field, value=self._value_for_type(field.field_type)
                    )
                )

        print("Execute bulk create")
        CustomField.objects.bulk_create(custom_fields)
        CustomValue.objects.bulk_create(custom_values)
        Person.objects.bulk_create(objects)

        print("Set many2many relations")
        for i in range(self.NUMBER_OF_OBJECTS):
            for c in range(self.NUMBER_OF_CUSTOM_FIELDS):
                field = custom_fields[c]
                objects[i].custom_values.add(CustomValue.objects.filter(field=field)[i])
