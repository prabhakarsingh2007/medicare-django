from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone



class Patient(models.Model):
    GENDER_CHOICES = (
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    hospital = models.ForeignKey('core.Hospital', on_delete=models.SET_NULL, null=True, blank=True, related_name='patients')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='patients/', blank=True, null=True)

    class Meta:
        db_table = 'careapp_patient'

    def __str__(self):
        return self.user.username

class HospitalAdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='hospital_admin_profile')
    hospital = models.ForeignKey('core.Hospital', on_delete=models.CASCADE, related_name='admin_profiles')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'careapp_hospitaladminprofile'

    def __str__(self):
        return f"{self.user.username} - {self.hospital.name}"


