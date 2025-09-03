from rest_framework.routers import DefaultRouter

from django_features.system_message.viewsets import SystemMessageTypeViewSet
from django_features.system_message.viewsets import SystemMessageViewSet


system_message_router = DefaultRouter(trailing_slash=False)
system_message_router.register(r"system_message", SystemMessageViewSet)
system_message_router.register(r"system_message_type", SystemMessageTypeViewSet)
