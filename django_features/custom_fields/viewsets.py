from django.db.models import QuerySet
from rest_framework.viewsets import ReadOnlyModelViewSet

from django_features.custom_fields import serializers
from django_features.custom_fields.helpers import get_custom_field_model


CustomFieldModel = get_custom_field_model()


class CustomFieldViewSet(ReadOnlyModelViewSet):
    queryset = CustomFieldModel.objects.all()
    serializer_class = serializers.CustomFieldSerializer

    valid_content_type_filter_fields = ["app_label", "model"]

    def get_queryset(self) -> QuerySet[CustomFieldModel]:
        qs = super().get_queryset()
        for field in self.valid_content_type_filter_fields:
            value = self.request.GET.get(field)
            if value:
                qs = qs.filter(**{f"content_type__{field}": value.lower()})
        return qs
