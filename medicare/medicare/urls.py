from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.http import HttpResponse
import os

def check_media(request):
    from django.conf import settings
    lines = []
    lines.append(f"Current Working Dir: {os.getcwd()}")
    lines.append(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
    lines.append(f"MEDIA_ROOT Exists: {os.path.exists(settings.MEDIA_ROOT)}")
    if os.path.exists(settings.MEDIA_ROOT):
        lines.append(f"MEDIA_ROOT Contents: {os.listdir(settings.MEDIA_ROOT)}")
        spec_dir = os.path.join(settings.MEDIA_ROOT, 'specialist')
        lines.append(f"specialist Dir Exists: {os.path.exists(spec_dir)}")
        if os.path.exists(spec_dir):
            lines.append(f"specialist Dir Contents: {os.listdir(spec_dir)}")
    return HttpResponse("<pre>" + "\n".join(lines) + "</pre>")

import tempfile

def check_logs(request):
    log_path = os.path.join(tempfile.gettempdir(), 'django_errors.log')
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse("<pre>" + content + "</pre>")
    return HttpResponse("No logs found.")


urlpatterns = [
    path('check-media/', check_media),
    path('check-logs/', check_logs),
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


