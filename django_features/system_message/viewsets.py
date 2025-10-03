from typing import Any

from django.db.models import Q
from django.db.models import QuerySet
from django.utils import timezone
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from django_filters.widgets import QueryArrayWidget
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.filters import SearchFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.viewsets import ReadOnlyModelViewSet

from django_features.pagination import PageNumberPaginator
from django_features.system_message import models
from django_features.system_message import serializers
from django_features.system_message.permissions import CanManageSystemMessage


class SystemMessageTypeViewSet(ReadOnlyModelViewSet):
    queryset = models.SystemMessageType.objects.all()
    serializer_class = serializers.SystemMessageTypeSerializer


class SystemMessageFilter(filters.FilterSet):
    active = filters.BooleanFilter(method="filter_active")
    dismissed = filters.BooleanFilter(method="filter_dismissed")
    type = filters.BaseInFilter(field_name="type", widget=QueryArrayWidget)

    class Meta:
        model = models.SystemMessage
        fields = ["id", "type"]

    def filter_active(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        q = Q(begin__lte=timezone.now()) & (
            Q(end__gte=timezone.now()) | Q(end__isnull=True)
        )
        if not value:
            return queryset.exclude(q)
        return queryset.filter(q)

    def filter_dismissed(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        if not self.request.user.is_authenticated:
            return queryset
        q = Q(dismissed_users=self.request.user)
        if not value:
            return queryset.exclude(q)
        return queryset.filter(q)


class SystemMessageViewSet(ModelViewSet):
    filter_backends = (OrderingFilter, DjangoFilterBackend, SearchFilter)
    filterset_class = SystemMessageFilter
    ordering_fields = (
        "background_color",
        "begin",
        "end",
        "order",
        "text",
        "text_color",
        "title",
        "type",
    )
    pagination_class = PageNumberPaginator
    permission_classes = [CanManageSystemMessage]
    queryset = models.SystemMessage.objects.all()
    search_fields = ("background_color", "message", "message_color", "title", "type")
    serializer_class = serializers.SystemMessageSerializer

    @action(methods=["patch"], detail=True)
    def dismiss(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> Response:
        if self.request.user.is_authenticated:
            self.get_object().dismissed_users.add(self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
