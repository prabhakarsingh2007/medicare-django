from django.contrib import admin
from .models import Specialist, Hospital, ActivityLog

admin.site.register(Specialist)
admin.site.register(Hospital)
admin.site.register(ActivityLog)
