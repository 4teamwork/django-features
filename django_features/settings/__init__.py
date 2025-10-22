from configurations import Configuration
from configurations import values


class BaseConfiguration(Configuration):
    @property
    def INSTALLED_APPS(self) -> list[str]:
        return []

    PAGE_QUERY_PARAM = values.Value("page")
    PAGE_SIZE_QUERY_PARAM = values.Value("page_size")

    CUSTOM_FIELD_APP = values.Value("django_features.custom_fields")

    @property
    def CUSTOM_FIELDS_FEATURE(self) -> bool:
        return self.CUSTOM_FIELD_APP in self.INSTALLED_APPS

    @property
    def CONSTANCE_ADDITIONAL_FIELDS(self) -> dict:
        return {
            "json": [
                "django_features.settings.fields.PrettyJSONField",
                {"required": False},
            ],
            "model_field_mapping": [
                "django_features.settings.fields.ModelFieldMapping",
                {"required": False},
            ],
        }
