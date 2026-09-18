from datetime import date
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db import models
from django.test.utils import isolate_apps
from rest_framework.fields import empty

from app.models import Person
from django_features.custom_fields.fields import ChoiceIdField
from django_features.custom_fields.models.field import AbstractBaseCustomField
from django_features.custom_fields.models.value import AbstractBaseCustomValue


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("primary_key_kind", ["integer_id", "uuid_id", "uuid_key"])
@isolate_apps("app.custom_field")
def test_alternate_models_and_reverse_relation(
    django_assert_num_queries: Any, primary_key_kind: str
) -> None:
    class AlternateField(AbstractBaseCustomField):
        class Meta:
            app_label = "custom_field"
            db_table = "contract_alternate_field"

    class AlternateValue(AbstractBaseCustomValue):
        if primary_key_kind == "uuid_id":
            id = models.UUIDField(primary_key=True, default=uuid4)
        elif primary_key_kind == "uuid_key":
            key = models.UUIDField(primary_key=True, default=uuid4)
        field = models.ForeignKey(
            AlternateField, related_name="options", on_delete=models.CASCADE
        )
        code = models.UUIDField(default=uuid4)
        day = models.DateField()
        instant = models.DateTimeField()
        amount = models.DecimalField(max_digits=8, decimal_places=2)

        class Meta:
            app_label = "custom_field"
            db_table = "contract_alternate_value"

    with connection.schema_editor() as editor:
        editor.create_model(AlternateField)
        editor.create_model(AlternateValue)
    try:
        field = AlternateField.objects.create(
            content_type=ContentType.objects.get_for_model(Person),
            identifier="alternate",
            label="Alternate",
            choice_field=True,
            field_type="CHAR",
        )
        choice = AlternateValue.objects.create(
            field=field,
            value="token",
            day=date(2026, 1, 2),
            instant=datetime(2026, 1, 2, 12, tzinfo=timezone.utc),
            amount=Decimal("12.50"),
        )
        with patch(
            "django_features.custom_fields.helpers.get_custom_value_model",
            return_value=AlternateValue,
        ), patch(
            "django_features.custom_fields.fields.get_custom_value_model",
            return_value=AlternateValue,
        ), django_assert_num_queries(
            2
        ):
            loaded = AlternateField.objects.with_choices().get(pk=field.pk)
            for unique_field in [None, "id", "pk", AlternateValue._meta.pk.name]:
                validator = ChoiceIdField(loaded, unique_field=unique_field)
                for value in [
                    choice.pk,
                    str(choice.pk),
                    {unique_field or "id": choice.pk},
                    {"id": str(choice.pk)},
                ]:
                    assert validator.run_validation(value) == choice
                loaded.multiple = True
                assert validator.run_validation([choice.pk]) == [choice]
                loaded.multiple = False
            assert (
                ChoiceIdField(loaded, unique_field="value").run_validation("token")
                == choice
            )
            for attribute in ["code", "day", "instant", "amount"]:
                value = getattr(choice, attribute)
                validator = ChoiceIdField(loaded, unique_field=attribute)
                for data in [value, str(value), {attribute: value}, {"id": value}]:
                    assert validator.run_validation(data) == choice
            for multiple in (False, True):
                loaded.multiple = multiple
                validator = ChoiceIdField(
                    loaded,
                    unique_field="value",
                    default=[str(choice.pk)] if multiple else str(choice.pk),
                )
                result = validator.run_validation(empty)
                assert result == ([choice] if multiple else choice)
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(AlternateValue)
            editor.delete_model(AlternateField)
