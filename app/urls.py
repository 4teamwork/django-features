from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import generic

from django_features.system_message.routers import system_message_router


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(system_message_router.urls)),
    path("", generic.RedirectView.as_view(url="./admin/")),
]
