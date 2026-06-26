from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import datetime

from doctors.models import Doctor
from appointments.models import Appointment
from core.models import Specialist
from notifications.notifications import (
    notify_appointment_booked,
    notify_appointment_confirmed,
    notify_appointment_cancelled,
)
from core.activity import log_activity
from core.views import get_current_hospital


@login_required(login_url='login')
def doctor_dashboard(request):
    doctor = Doctor.objects.select_related('hospital', 'specialist').filter(user=request.user).first()
    if not doctor:
        messages.error(request, "Doctor profile not found.")
        return redirect('home')

    if doctor.hospital_id:
        request.session["hospital_id"] = doctor.hospital_id

    appointments = Appointment.objects.filter(doctor=doctor).select_related('user__patient').order_by('-date', '-time')

    return render(request, 'doctors/doctor_dashboard.html', {
        "doctor": doctor,
        "appointments": appointments
    })


@login_required(login_url='login')
def doctor_update_appointment_status(request, id, status):
    if request.method != "POST":
        return redirect("doctor_dashboard")

    doctor = Doctor.objects.filter(user=request.user).first()
    if not doctor:
        messages.error(request, "Doctor profile not found.")
        return redirect("doctor_dashboard")

    allowed_statuses = {"Confirmed", "Cancelled", "Pending"}
    if status not in allowed_statuses:
        messages.error(request, "Invalid status.")
        return redirect("doctor_dashboard")

    appointment = get_object_or_404(Appointment, id=id, doctor=doctor)
    appointment.status = status
    appointment.save()

    if status == "Confirmed":
        notify_appointment_confirmed(appointment)
    elif status == "Cancelled":
        notify_appointment_cancelled(appointment, cancelled_by="doctor")

    log_activity(
        actor=request.user,
        action="appointment_status_updated",
        target_type="appointment",
        target_id=str(appointment.id),
        description=f"Doctor updated appointment status to {status}",
        extra_data={"status": status, "doctor_id": appointment.doctor_id},
    )

    messages.success(request, f"Appointment marked as {status}.")
    return redirect("doctor_dashboard")


@login_required(login_url='login')
def doctor_reschedule_appointment(request, id):
    doctor = Doctor.objects.filter(user=request.user).first()
    if not doctor:
        messages.error(request, "Doctor profile not found.")
        return redirect('doctor_dashboard')

    appointment = get_object_or_404(Appointment, id=id, doctor=doctor)

    if request.method == "POST":
        date_str = request.POST.get("date")
        time_str = request.POST.get("time")
        try:
            new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            new_time = datetime.strptime(time_str, "%H:%M").time()
        except Exception:
            messages.error(request, "Invalid date or time format.")
            return redirect('doctor_dashboard')

        now_local = timezone.localtime(timezone.now())
        if new_date < now_local.date() or (new_date == now_local.date() and new_time <= now_local.time()):
            messages.error(request, "Cannot reschedule to a past date/time.")
            return redirect('doctor_dashboard')

        if Appointment.objects.filter(doctor=doctor, date=new_date, time=new_time).exclude(id=appointment.id).exclude(status="Cancelled").exists():
            messages.error(request, "Selected slot already booked.")
            return redirect('doctor_dashboard')

        appointment.date = new_date
        appointment.time = new_time
        appointment.status = "Pending"
        appointment.save(update_fields=["date", "time", "status"])

        notify_appointment_booked(appointment)
        log_activity(
            actor=request.user,
            action="appointment_rescheduled",
            target_type="appointment",
            target_id=str(appointment.id),
            description=f"Doctor rescheduled appointment to {new_date} {new_time}",
            extra_data={"doctor_id": doctor.id, "new_date": str(new_date), "new_time": str(new_time)},
        )
        messages.success(request, "Appointment rescheduled successfully.")
        return redirect('doctor_dashboard')

    return render(request, "doctors/doctor_reschedule.html", {"appointment": appointment})


def doctor_profile(request, slug):
    doctor = get_object_or_404(Doctor, slug=slug)
    if doctor.hospital:
        request.session["hospital_id"] = doctor.hospital.id
    return render(request, "doctors/doctor_profile.html", {"doctor": doctor})


def specialist_doctors(request, id):
    current_hospital = get_current_hospital(request)

    # Find the specialist — if hospital is selected, only show that hospital's specialist
    specialist_qs = Specialist.objects.filter(id=id)
    if current_hospital:
        specialist_qs = specialist_qs.filter(hospital=current_hospital)
    specialist = get_object_or_404(specialist_qs)

    # Only show doctors from the selected hospital
    doctors = Doctor.objects.filter(specialist=specialist)
    if current_hospital:
        doctors = doctors.filter(hospital=current_hospital)
    else:
        doctors = doctors.all()

    return render(request, "doctors/doctors.html", {
        "specialist": specialist,
        "doctors": doctors,
        "current_hospital": current_hospital,
    })
