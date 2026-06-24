from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid
from datetime import timedelta
from django.utils import timezone


def default_email_token_expiry():
    return timezone.now() + timedelta(hours=24)

# Create your models here.


class Specialist(models.Model):
    hospital = models.ForeignKey('Hospital', on_delete=models.CASCADE, null=True, blank=True, related_name='specialists')
    name = models.CharField(max_length=100)
    icon = models.ImageField(upload_to='specialist/', blank=True, null=True)

    def __str__(self):
        return self.name

class Hospital(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        base_slug = slugify(self.name) if self.name else "hospital"
        slug_candidate = base_slug
        count = 1

        while Hospital.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
            slug_candidate = f"{base_slug}-{count}"
            count += 1

        self.slug = slug_candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class HospitalAdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='hospital_admin_profile')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='admin_profiles')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.hospital.name}"


class Patient(models.Model):
    GENDER_CHOICES = (
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    hospital = models.ForeignKey('Hospital', on_delete=models.SET_NULL, null=True, blank=True, related_name='patients')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='patients/', blank=True, null=True)

    def __str__(self):
        return self.user.username


class Doctor(models.Model):
    name = models.CharField(max_length=100)
    hospital = models.ForeignKey('Hospital', on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors')
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE)
    experience = models.IntegerField()
    qualification = models.CharField(max_length=200)
    fees = models.IntegerField(null=True, blank=True)
    availability = models.CharField(max_length=100,null=True, blank=True)
    about = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="doctors/")
    slug = models.SlugField(unique=True,null=True, blank=True)

    def save(self, *args, **kwargs):
        base_slug = slugify(self.name) if self.name else "doctor"
        slug_candidate = base_slug
        count = 1

        while Doctor.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
            slug_candidate = f"{base_slug}-{count}"
            count += 1

        self.slug = slug_candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Appointment(models.Model):
    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    hospital = models.ForeignKey('Hospital', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE, related_name="appointments")
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
        unique_together = ("doctor", "date", "time")
        ordering = ["-date", "-time"]

    def __str__(self):
        return f"{self.name} - {self.doctor.name}"


class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=200)
    order_id = models.CharField(max_length=200)
    amount = models.IntegerField()
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.payment_id

    amount = models.IntegerField()

    status = models.BooleanField(default=False)


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_tokens')
    token = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_email_token_expiry)
    used_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.token}"


class ActivityLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')
    actor_role = models.CharField(max_length=30, default='system')
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.actor_role} - {self.action}"
