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

Each app includes its own translation catalogs, which Django discovers through
`INSTALLED_APPS`. No package-specific `LOCALE_PATHS` entry is needed.

If you use the shared serializer fields in `django_features.fields`, also add
`django_features` to `INSTALLED_APPS` to load their translations. The two feature
apps do not require this root app.

Django merges installed apps' translation catalogs; translations are not scoped
to the app that provides them. In German, the custom-fields catalog translates
the context-free message `Label` as `Bezeichnung`, which can also affect the same
message in other apps. To override it, provide a translation in a project catalog
in `LOCALE_PATHS` or in an app listed before `django_features.custom_fields` in
`INSTALLED_APPS`.

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

## Translations

Catalogs live in each feature app's `locale/` directory. Shared serializer-field
messages remain in `django_features/locale/`, and demo-only messages live in
`app/locale/`. Keep translations of messages shared between apps consistent.

From the repository root, update the catalogs with:

```bash
poetry run ./bin/i18n_update
```

This requires GNU gettext. Edit the German, English, and French `.po` files as
needed, then run the command again to compile them. Commit both `.po` and `.mo`
files; the compiled package catalogs are included in the distribution so consumers
do not need to run `compilemessages`.

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

## Custom-field upgrade

`AbstractBaseCustomValue` provides the optional, untranslated `external_key` field.
It stores the stable token supplied by the external system, independently of the
display label and application value. It replaces `external_label` from 2026.5.0.
Every concrete subclass upgrading from that release needs a `RenameField`
migration, plus removal and recreation of any constraint that names the old field.
The example app's `0003_rename_external_choice_key` demonstrates a reversible
upgrade that preserves existing keys and values. New consumers need an `AddField`
migration. Apply consumer migrations before starting application workers with the
upgraded package; do not add this field to modeltranslation.

If non-empty external keys must be unique within a field, add this constraint
to the concrete value model's `Meta.constraints` before generating migrations,
using a unique constraint name:

```python
from django.db import models

models.UniqueConstraint(
    fields=["field", "external_key"],
    condition=~models.Q(external_key=""),
    name="custom_value_field_external_key_unique",
)
```

## Matching choices

For a choice field `field`, match the external system's token directly against
the choice's exact `external_key`, without language or matching configuration:

```python
from django_features.custom_fields.matching import ChoiceMatcher

matcher = ChoiceMatcher(field.choices)
choice = matcher.resolve(external_token)
```

Generic callers can still use `attribute="value"`, or `attribute="label"` with
an explicit configured `language`. When loading several fields, use the custom-field
queryset's `with_choices()` to prefetch their choices.

Matching skips `None` and empty-string keys after normalization. Duplicate keys
raise an ambiguous-match validation error only when resolved; unique keys remain
matchable. Empty or unknown keys raise a missing-match validation error.
