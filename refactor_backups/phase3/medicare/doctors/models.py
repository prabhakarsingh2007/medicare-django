from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class Doctor(models.Model):
    name = models.CharField(max_length=100)
    hospital = models.ForeignKey('core.Hospital', on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors')
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    specialist = models.ForeignKey('core.Specialist', on_delete=models.CASCADE)
    experience = models.IntegerField()
    qualification = models.CharField(max_length=200)
    fees = models.IntegerField(null=True, blank=True)
    availability = models.CharField(max_length=100, null=True, blank=True)
    about = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to="doctors/")
    slug = models.SlugField(unique=True, null=True, blank=True)

    class Meta:
        db_table = 'careapp_doctor'

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
