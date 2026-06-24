from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class Specialist(models.Model):
    hospital = models.ForeignKey('Hospital', on_delete=models.CASCADE, null=True, blank=True, related_name='specialists')
    name = models.CharField(max_length=100)
    icon = models.ImageField(upload_to='specialist/', blank=True, null=True)

    class Meta:
        db_table = 'careapp_specialist'

    def __str__(self):
        return self.name

class Hospital(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'careapp_hospital'

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
        db_table = 'careapp_activitylog'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.actor_role} - {self.action}"
