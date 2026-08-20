# django-features
A collection of fearures used in our Django-based web applications

[Changelog](CHANGELOG.md)

# Installation

``` bash
pip install ftw-django-features
```

# Usage

Add desired app to `INSTALLED_APPS` in your Django project.

Available apps:
```
django_features.system_message
django_features.custom_fields
```

# Configuration

If you want to use `django_features`, your base configuration class should inherit from `django_features.settings.BaseConfiguration`.

```
from django_features.settings import BaseConfiguration


class Base(BaseConfiguration):
    ...
```

## Custom Fields

To use all features of the `django_features.custom_fields` app, the following steps are required:

Add the `django_features.custom_fields.routers.custom_field_router` to your `ROOT_URLCONF`. For example:

```
path("api/", include(custom_field_router.urls)),
```

### Create your own custom field and value models

1. You need to create a custom field model and a custom value model.
2. Your custom field model should inherit from `django_features.custom_fields.models.field.AbstractBaseCustomField`.
3. Your custom value model should inherit from `django_features.custom_fields.models.value.AbstractBaseCustomValue`.

### Configuration

- You can configure the models used by the `django_features.custom_fields` app by setting the `CUSTOM_FIELD_MODEL` or `CUSTOM_FIELD_VALUE_MODEL` setting.
- The swapped models should inherit from `django_features.custom_fields.models.field.AbstractBaseCustomField` or `django_features.custom_fields.models.value.AbstractBaseCustomValue`.

### Models with custom values

1. Your models with custom values should inherit from `django_features.custom_fields.models.CustomFieldBaseModel`.
2. Your models should have a relation to the custom value model. For example:
    - `custom_values = models.ManyToManyField(blank=True, to=CustomValue, verbose_name=_("Benutzerdefinierte Werte"))`

#### Querysets

Your querysets for the models with custom values should inherit from `django_features.custom_fields.models.CustomFieldModelBaseManager`.

#### Serializers

Your serializers for the models with custom values should inherit from `django_features.custom_fields.serializers.CustomFieldBaseModelSerializer`.

The serializer adds the applicable custom fields to the fields declared in
`Meta.fields`. To restrict custom fields to a model type, configure the relation
which identifies that type on the model:

```python
class Person(CustomFieldBaseModel):
    _custom_field_type_attr = "person_type"

    person_type = models.ForeignKey(
        PersonType,
        null=True,
        on_delete=models.SET_NULL,
    )
```

Custom fields without a `type_id` apply to every `Person`. A custom field with a
`type_content_type` and `type_id` only applies when the selected `person_type`
matches both values.

The serializer reads the selected type from `_custom_field_type_attr` by default:

```python
class PersonSerializer(CustomFieldBaseModelSerializer):
    class Meta:
        model = Person
        fields = ["email", "firstname", "lastname", "person_type"]
```

For input that exposes the type under another name, set
`custom_field_type_input_field` or override `get_custom_field_type_id()`:

```python
class PersonSerializer(CustomFieldBaseModelSerializer):
    custom_field_type_input_field = "type_id"

    type_id = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=PersonType.objects.all(),
        required=False,
        source="person_type",
    )

    class Meta:
        model = Person
        fields = ["email", "firstname", "lastname", "type_id"]
```

The configured input field must be writable and map through `source` to the
model relation named by `_custom_field_type_attr` (or its `<relation>_id`
attribute). Undeclared and read-only input cannot select type-specific custom
fields.

The input field's normal representation is supported, including alternative
lookups such as `SlugRelatedField`. A field whose `source` is the model relation
must validate to an instance of the related type model. A field whose `source`
is the `<relation>_id` attribute must instead validate to a scalar primary key;
the serializer verifies that the selected object exists. Incompatible field and
source combinations raise `ImproperlyConfigured` during validation rather than
failing when the model is saved.

On updates, the submitted type takes precedence over the instance type. If the
type is omitted, the instance type is used. With `many=True`, every input or
instance is evaluated separately, so heterogeneous lists are supported. A custom
`Meta.list_serializer_class` must inherit from `CustomFieldListSerializer` to
retain this per-item behavior. `ListDataMappingSerializer` already provides this
behavior and applies mapping hooks once for each original list item. By default,
list-level validation must preserve the number, position, and identity of those
validated items (returning a new list containing the same items is supported). A
specialized list serializer that intentionally reorders, replaces, adds, or
removes items must override `get_paired_item_serializers()` and return the child
serializer paired with every item in the resulting list. List validation and
`save()` keyword arguments may not change an item's selected type after its
type-specific fields have been validated.

DRF defaults configured on the type input field select the applicable custom
fields on creates and full updates. As with other DRF fields, defaults are not
applied during partial updates. Context-aware selector defaults may inspect the
serializer's static fields, but cannot depend on type-specific dynamic fields
because those fields cannot be selected until the default resolves the type.

Changing an object's type does not delete stored values belonging to its previous
type. Those values are omitted from serialization and cannot be submitted while
the new type is selected.

The following hooks can be overridden for application-specific behavior:

- `get_custom_fields_queryset()` filters or replaces the applicable custom-field
  queryset.
- `get_custom_field_type_id()` resolves the selected type.
- `get_custom_fields_cache_key()` identifies definition sets that may safely be
  shared between list items. Override it when custom field selection depends on
  additional per-item state.
- `should_validate_custom_field_type_selection()` can defer the final
  selector/source consistency check for serializers which intentionally persist
  an intermediate relation value, such as `MappingSerializer`.
- `is_custom_field_writable(custom_field)` controls whether submitted values may
  change a field. It returns `custom_field.editable` by default.
- `for_item(instance=..., data=...)` constructs serializers used by `many=True`.
  Serializers with extra constructor arguments should override it and retain the
  shared custom-field definition cache.
- `CustomFieldListSerializer.get_paired_item_serializers(validated_data)` defines
  how the per-item serializers are paired after list-level validation. Override
  it when a custom list validator intentionally changes item positions or
  identities.

For example, an optional constructor value used by custom hooks can be copied to
each per-item serializer after the base implementation has preserved the normal
serializer options and shared cache:

```python
class TenantPersonSerializer(PersonSerializer):
    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)

    def for_item(self, instance=None, data=serializers.empty):
        serializer = super().for_item(instance=instance, data=data)
        serializer.tenant = self.tenant
        return serializer
```

Pass `exclude_custom_fields=True` to omit dynamic custom fields. Package-specific
serializer options such as `exclude_custom_fields` and `write_only_serializer`
are consumed by the base serializer and are not forwarded to Django REST
Framework. Mapping serializers also ignore mapped custom-field values when
custom fields are excluded, while continuing to process ordinary model mappings.
Custom-field identifiers must not collide with model fields, relation attnames,
model/runtime attributes, or writable serializer field names and sources. Such
configuration is rejected before annotations or serializer fields are built,
including for filtered, type-specific, and excluded definitions.

Submitted values for a different type and values for fields with
`editable=False` are rejected with field-specific validation errors. Trusted
application flows that need to write managed fields can override
`is_custom_field_writable()`. Custom-field defaults are create-only. Full and
partial updates preserve every omitted custom value, regardless of editability,
and never apply or create a custom-field default. Defaults configured on ordinary
declared DRF fields, including a type selector, retain DRF's normal behavior. The
generated serializer fields also enforce the custom-field configuration for
`required`, `default`, `allow_null`, `allow_blank`, choices, and multiple values.

Choice input may be a scalar lookup value or an object containing the configured
`_unique_choice_field` (which defaults to `id`). Multiple-choice input must be a
list and cannot contain duplicate lookup values. Invalid, missing, ambiguous, and
duplicate choices produce validation errors instead of database exceptions.
Lookup comparison follows the Django model field and preserves JSON type identity,
so booleans, integers, and floating-point JSON values with equal Python values
remain distinct.

Configured choice defaults use `CustomValue` primary keys (a scalar for a single
choice or a list for multiple choices), independently of `_unique_choice_field`.
Request payloads continue to use the serializer's configured choice lookup.

`CustomFieldSerializer` exposes the validation and type metadata clients need to
build compatible forms, including `allow_blank`, `allow_null`, `default`,
`editable`, `required`, `type_content_type`, and `type_id`.

#### Compatibility and upgrade notes

The supported and continuously tested combinations are:

| Django | Python | Django REST Framework |
| --- | --- | --- |
| Latest 4.2 patch | 3.12 | Latest 3.17 patch (`>3.17,<3.18`) |
| Latest 5.2 patch | 3.13 | Latest 3.17 patch (`>3.17,<3.18`) |

Upgrading requires Django REST Framework 3.17.1 or newer, but not 3.18. Existing
custom serializers should also be checked for the following behavioral contracts:

- A type selector must be a writable field whose `source` persists the configured
  type relation or its `<relation>_id` attribute.
- A custom `Meta.list_serializer_class` must inherit from
  `CustomFieldListSerializer`. List validators which change item identity, order,
  or cardinality must implement `get_paired_item_serializers()`.
- Values submitted for another type or for `editable=False` fields now produce
  field-specific validation errors instead of being accepted.
- Custom-field defaults apply only when creating an object. Full and partial
  updates preserve omitted custom values and do not apply custom-field defaults.
  Ordinary declared DRF field defaults retain DRF's normal create/full-update and
  partial-update behavior.

Built distributions include compiled German, English, and French gettext catalogs;
consumers do not need to compile package translations separately.

## System Message

If you want to use `django_features.system_message`, your base configuration class should inherit from `django_features.system_message.settings.SystemMessageConfigurationMixin`.

Then call the super property:

```
@property
def CONSTANCE_CONFIG(self) -> dict:
    config = super().CONSTANCE_CONFIG
    return {**config, ...}

@property
def CONSTANCE_CONFIG_FIELDSETS(self) -> dict:
    config = super().CONSTANCE_CONFIG_FIELDSETS
    return {
        **config,
        ...
    }
```

Add the `django_features.system_message.routers.system_message_router` to your `ROOT_URLCONF`. For example:

```
path("api/", include(system_message_router.urls)),
```

# Development

Installing dependencies, assuming you have poetry installed:

``` bash
poetry install
```

# Release

This package uses towncrier to manage the changelog, and to introduce new changes, a file with a concise title and a brief explanation of what the change accomplishes should be created in the `changes` directory, with a suffix indicating whether the change is a feature, bugfix, or other.

To make a release and publish it to PyPI, the following command can be executed:

``` bash
./bin/release
```

This script utilizes zest.releaser and towncrier to create the release, build the wheel, and publish it to PyPI.

Before running the release command, it is necessary to configure poetry with an access token for PyPI by executing the following command and inserting the token stored in 1password:

``` bash
poetry config pypi-token.pypi <token>
```

The `version` attribute in the `pyproject.toml` file should be updated to the new version before running the release command, because this version will be published to PyPI.
