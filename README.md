# django-features
A collection of fearures used in our Django-based web applications

[Changelog](CHANGELOG.md)

## Installation

``` bash
pip install ftw-django-features
```

## Usage

Add desired app to `INSTALLED_APPS` in your Django project.

Available apps:
```
django_features.system_message
django_features.custom_fields
```

## Configuration

If you want to use `django_features`, your base configuration class should inherit from `django_features.settings.BaseConfiguration`.

```
from django_features.settings import BaseConfiguration


class Base(BaseConfiguration):
    ...
```

### Custom Fields

To use all features of the `django_features.custom_fields` app, the following steps are required:

Add the `django_features.custom_fields.routers.custom_field_router` to your `ROOT_URLCONF`. For example:

```
path("api/", include(custom_field_router.urls)),
```

#### Models

Your models should inherit from `django_features.custom_fields.models.CustomFieldBaseModel`.

#### Querysets

Your querysets should inherit from `django_features.custom_fields.models.CustomFieldModelBaseManager`.

#### Serializers

Your serializers should inherit from `django_features.custom_fields.serializers.CustomFieldBaseModelSerializer`.

### System Message

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

## Development

Installing dependencies, assuming you have poetry installed:

``` bash
poetry install
```

## Release

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
