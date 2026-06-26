from django.contrib import admin
from .models import MedicalRecord

@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'patient', 'doctor', 'hospital', 'record_type', 'created_at')
    list_filter = ('record_type', 'hospital', 'created_at')
    search_fields = ('title', 'patient__name', 'doctor__name', 'description')
