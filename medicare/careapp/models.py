from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.


class Specialist(models.Model):
    name = models.CharField(max_length=100)
    icon = models.ImageField(upload_to='specialist/', blank=True, null=True)

    def __str__(self):
        return self.name

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()

    def __str__(self):
        return self.user.username


class Doctor(models.Model):
    name = models.CharField(max_length=100)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE)
    experience = models.IntegerField()
    qualification = models.CharField(max_length=200)
    fees = models.IntegerField(null=True, blank=True)
    availability = models.CharField(max_length=100,null=True, blank=True)
    about = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="doctors/")
    slug = models.SlugField(unique=True,null=True, blank=True)

    def __str__(self):
        return self.name


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Appointment(models.Model):
    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
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
    








class Ambulance(models.Model):
    name = models.CharField(max_length=100)
    ambulance_type = models.CharField(max_length=100)
    driver_name = models.CharField(max_length=100)
    driver_phone = models.CharField(max_length=15)
    status = models.CharField(max_length=50, default="Available")

    def __str__(self):
        return self.name


class AmbulanceBooking(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    ambulance = models.ForeignKey(Ambulance, on_delete=models.CASCADE)

    pickup_location = models.CharField(max_length=200)
    drop_location = models.CharField(max_length=200)

    date = models.DateField()
    time = models.TimeField()

    status = models.CharField(max_length=50, default="Pending")

    def __str__(self):
        return str(self.patient)



class LabTest(models.Model):
    test_name = models.CharField(max_length=150)
    price = models.IntegerField()
    description = models.TextField()

    def __str__(self):
        return self.test_name


class LabBooking(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE)

    date = models.DateField()
    time = models.TimeField()
    address = models.CharField(max_length=200)

    status = models.CharField(max_length=50, default="Pending")

    def __str__(self):
        return str(self.patient)


class Medicine(models.Model):
    name = models.CharField(max_length=150)
    price = models.IntegerField()
    stock = models.IntegerField()
    expiry_date = models.DateField()

    def __str__(self):
        return self.name


class MedicineOrder(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)

    quantity = models.IntegerField()
    address = models.CharField(max_length=200)

    order_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=50, default="Pending")

    def __str__(self):
        return str(self.patient)

    