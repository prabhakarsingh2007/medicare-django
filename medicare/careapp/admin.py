from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Specialist)
admin.site.register(Doctor)
admin.site.register(Appointment)
admin.site.register(Payment)
admin.site.register(Patient)
admin.site.register(Hospital)
admin.site.register(HospitalAdminProfile)
admin.site.register(EmailVerificationToken)
admin.site.register(ActivityLog)
                       

