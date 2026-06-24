from django.urls import path
from .views import (
    doctor_dashboard,
    doctor_update_appointment_status,
    doctor_reschedule_appointment,
    doctor_profile,
    specialist_doctors,
)

urlpatterns = [
    path("doctor_dashboard/", doctor_dashboard, name="doctor_dashboard"),
    path("doctor/appointment/<int:id>/status/<str:status>/", doctor_update_appointment_status, name="doctor_update_appointment_status"),
    path("doctor/appointment/<int:id>/reschedule/", doctor_reschedule_appointment, name="doctor_reschedule_appointment"),
    path("doctor_profile/<slug:slug>/", doctor_profile, name="doctor_profile"),
    path("specialist_doctors/<int:id>/", specialist_doctors, name="specialist_doctors"),
]
