from django.contrib import admin
# pyrefly: ignore [missing-import]
from .models import Appointment

admin.site.register(Appointment)
