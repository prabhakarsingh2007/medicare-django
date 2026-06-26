from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from accounts.models import Patient
from doctors.models import Doctor
from core.models import Hospital

class MedicalRecord(models.Model):
    RECORD_TYPES = (
        ('Prescription', 'Prescription'),
        ('Lab Report', 'Lab Report'),
        ('Diagnostic', 'Diagnostic'),
        ('Vaccination', 'Vaccination'),
        ('Other', 'Other'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_records')
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_records')
    title = models.CharField(max_length=200)
    record_type = models.CharField(max_length=50, choices=RECORD_TYPES, default='Other')
    description = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to='ehr/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'careapp_medicalrecord'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.patient.name}"
