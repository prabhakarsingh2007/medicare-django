from django.urls import path
# pyrefly: ignore [missing-import]
from .views import (
    book_appointment,
    get_booked_slots,
    edit_appointment,
    cancel_appointment,
    my_appointments,
    patient_dashboard,
    download_appointment_slip,
)

urlpatterns = [
    path("book_appointment/<slug:slug>/", book_appointment, name='book_appointment'),
    path("booked_slots/", get_booked_slots, name='booked_slots'),
    path("edit_appointment/<int:id>/", edit_appointment, name="edit_appointment"),
    path("cancel_appointment/<int:id>/", cancel_appointment, name="cancel_appointment"),
    path("patient_dashboard/", patient_dashboard, name="patient_dashboard"),
    path("patient/my_appointments", my_appointments, name="my_appointments"),
    path("patient/appointment/<int:id>/download-slip/", download_appointment_slip, name="download_appointment_slip"),
]
