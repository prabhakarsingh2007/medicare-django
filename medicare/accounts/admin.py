from django.contrib import admin
from .models import Patient, HospitalAdminProfile

admin.site.register(Patient)
admin.site.register(HospitalAdminProfile)

