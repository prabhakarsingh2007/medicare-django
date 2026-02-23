from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Specialist)
admin.site.register(Doctor)
admin.site.register(Appointment)
admin.site.register(Payment)
admin.site.register(Ambulance)
admin.site.register(AmbulanceBooking)
admin.site.register(LabTest)
admin.site.register(LabBooking)
admin.site.register(Medicine)
admin.site.register(MedicineOrder)  
admin.site.register(Patient)
                       

