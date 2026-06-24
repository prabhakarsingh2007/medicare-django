from django.db import models
from django.contrib.auth.models import User

class Appointment(models.Model):
    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    hospital = models.ForeignKey('core.Hospital', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.CASCADE, related_name="appointments")
    name = models.CharField("Full Name", max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    date = models.DateField()
    time = models.TimeField()
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'careapp_appointment'
        unique_together = ("doctor", "date", "time")
        ordering = ["-date", "-time"]

    def __str__(self):
        return f"{self.name} - {self.doctor.name}"
