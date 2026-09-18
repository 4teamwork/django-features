from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from app.models import Person


@pytest.mark.django_db(transaction=True)
def test_external_label_upgrade_preserves_existing_values(pytestconfig: Any) -> None:
    if pytestconfig.getoption("nomigrations", default=False):
        pytest.skip("Run with --migrations to exercise the historical schema.")
    content_type_id = ContentType.objects.get_for_model(Person).pk
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    old_target = [("custom_field", "0001_inherit_from_custom_base_model")]
    try:
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        field = old_apps.get_model("custom_field", "CustomField").objects.create(
            identifier="migration_field",
            content_type_id=content_type_id,
            field_type="CHAR",
            label="Field",
        )
        old = old_apps.get_model("custom_field", "CustomValue").objects.create(
            field_id=field.pk, value="stable"
        )
        executor = MigrationExecutor(connection)
        executor.migrate(leaves)
        new_apps = executor.loader.project_state(leaves).apps
        upgraded = new_apps.get_model("custom_field", "CustomValue").objects.get(
            pk=old.pk
        )
        assert upgraded.external_label == ""
        assert upgraded.value == "stable"
        upgraded.external_label = "external"
        upgraded.save()
        upgraded.refresh_from_db()
        assert upgraded.external_label == "external"
    finally:
        MigrationExecutor(connection).migrate(leaves)
