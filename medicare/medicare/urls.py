from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('superadmin/', admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("doctors.urls")),
    path("", include("appointments.urls")),
    path("", include("payments.urls")),
    path("", include("dashboard.urls")),
    path("", include("ehr.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
