from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import generic

from django_features.system_message.routers import system_message_router


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(system_message_router.urls)),
    path("", generic.RedirectView.as_view(url="./admin/")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
