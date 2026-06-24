from django.contrib import admin
from .models import Patient, HospitalAdminProfile, EmailVerificationToken

admin.site.register(Patient)
admin.site.register(HospitalAdminProfile)
admin.site.register(EmailVerificationToken)
