from django.db.models import QuerySet
from rest_framework.viewsets import ReadOnlyModelViewSet

from django_features.custom_fields import models
from django_features.custom_fields import serializers


class CustomFieldViewSet(ReadOnlyModelViewSet):
    queryset = models.CustomField.objects.all()
    serializer_class = serializers.CustomFieldSerializer

    valid_content_type_filter_fields = ["app_label", "model"]

    def get_queryset(self) -> QuerySet[models.CustomField]:
        qs = super().get_queryset()
        for field in self.valid_content_type_filter_fields:
            value = self.request.GET.get(field)
            if value:
                qs = qs.filter(**{f"content_type__{field}": value.lower()})
        return qs
