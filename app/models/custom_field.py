from app.web.publishable import PublishableModel
from app.web.publishable import PublishableQuerySet
from django_features.custom_fields.models import CustomField
from django_features.custom_fields.models.field import CustomFieldQuerySet


class ExtendedCustomFieldQuerySet(CustomFieldQuerySet, PublishableQuerySet):
    pass


class ExtendedCustomField(CustomField, PublishableModel):
    objects = ExtendedCustomFieldQuerySet.as_manager()

    class Meta(CustomField.Meta):
        pass
