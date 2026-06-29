from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    path('superadmin/', admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("doctors.urls")),
    path("", include("appointments.urls")),
    path("", include("payments.urls")),
    path("", include("dashboard.urls")),
    path("", include("ehr.urls")),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

