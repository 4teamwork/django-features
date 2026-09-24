from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [("custom_field", "0002_add_external_label_constraint")]

    operations = [
        migrations.RemoveConstraint(
            model_name="customvalue", name="custom_value_field_external_label_unique"
        ),
        migrations.RenameField(
            model_name="customvalue", old_name="external_label", new_name="external_key"
        ),
        migrations.AlterField(
            model_name="customvalue",
            name="external_key",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Externer Schlüssel",
            ),
        ),
        migrations.AddConstraint(
            model_name="customvalue",
            constraint=models.UniqueConstraint(
                fields=("field", "external_key"),
                condition=~models.Q(external_key=""),
                name="custom_value_field_external_key_unique",
            ),
        ),
    ]
