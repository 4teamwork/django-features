from rest_framework.routers import DefaultRouter

from django_features.custom_fields.viewsets import CustomFieldViewSet


custom_field_router = DefaultRouter(trailing_slash=False)
custom_field_router.register(r"custom_field", CustomFieldViewSet)
