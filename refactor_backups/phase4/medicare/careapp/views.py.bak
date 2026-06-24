from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

# ...existing imports...

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

    # GET: show reschedule form
    return render(request, "doctor/doctor_reschedule.html", {"appointment": appointment})
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.urls import reverse
from django.utils.crypto import get_random_string
import re
from io import BytesIO

from datetime import datetime, timedelta, time
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

import razorpay

from .models import *
from .notifications import (
    notify_appointment_booked,
    notify_appointment_confirmed,
    notify_appointment_cancelled,
    send_email_notification,
)
from .security_utils import is_strong_password, PASSWORD_RULE_TEXT
from .activity import log_activity


# ================= RAZORPAY CLIENT =================
client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


def is_valid_indian_phone(phone):
    return bool(re.fullmatch(r"\d{10}", phone or ""))


def is_valid_email_address(email):
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def build_unique_username_from_email(email):
    base = (email.split("@")[0] or "patient").strip().lower()
    base = re.sub(r"[^a-z0-9_]", "", base)[:20] or "patient"
    candidate = base
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}_{get_random_string(4).lower()}"
    return candidate


def is_patient_profile_complete(patient):
    if not patient:
        return False
    required_fields = [patient.name, patient.email, patient.phone, patient.age, patient.gender]
    return all(required_fields)


def _login_lock_key(request, username):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
    return f"login-lock:{ip}:{(username or '').lower()}"


def is_login_locked(request, username):
    lock_key = _login_lock_key(request, username)
    attempts = cache.get(lock_key, 0)
    return attempts >= int(getattr(settings, "LOGIN_MAX_ATTEMPTS", 5))


def register_login_failure(request, username):
    lock_key = _login_lock_key(request, username)
    attempts = cache.get(lock_key, 0) + 1
    timeout = int(getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900))
    cache.set(lock_key, attempts, timeout=timeout)


def clear_login_failures(request, username):
    cache.delete(_login_lock_key(request, username))


def get_current_hospital(request):
    selected_slug = request.GET.get("hospital")
    hospital_id = request.session.get("hospital_id")
    hospital = None

    try:
        if selected_slug:
            hospital = Hospital.objects.filter(slug=selected_slug, is_active=True).first()
        elif hospital_id:
            hospital = Hospital.objects.filter(id=hospital_id, is_active=True).first()

        if not hospital:
            hospital = Hospital.objects.filter(is_active=True).order_by("name").first()

        if hospital:
            request.session["hospital_id"] = hospital.id
    except (OperationalError, ProgrammingError):
        # Keep site usable if hospital tables are not ready yet in a fresh deploy.
        return None

    return hospital


# ================= HOME =================
def home(request):
    current_hospital = get_current_hospital(request)

    try:
        specialists_qs = Specialist.objects.all()

        if current_hospital:
            specialists_qs = specialists_qs.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True))

        # Evaluate queries here so migration-related DB errors are caught gracefully.
        specialists = list(specialists_qs)
        hospitals = list(Hospital.objects.filter(is_active=True).order_by("name"))
    except (OperationalError, ProgrammingError):
        specialists = []
        hospitals = []
        current_hospital = None

    return render(request, "home.html", {
        "specialists": specialists,
        "hospitals": hospitals,
        "current_hospital": current_hospital,
    })


# ================= DOCTOR =================
@login_required(login_url='login')
def doctor_dashboard(request):
    doctor = Doctor.objects.select_related('hospital', 'specialist').filter(user=request.user).first()
    if not doctor:
        messages.error(request, "Doctor profile not found.")
        return redirect('home')

    # Keep session hospital aligned with logged-in doctor to avoid cross-hospital filtering issues.
    if doctor.hospital_id:
        request.session["hospital_id"] = doctor.hospital_id

    appointments = Appointment.objects.filter(doctor=doctor).order_by('-date', '-time')

    return render(request, 'doctor/doctor_dashboard.html', {
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


def doctor_profile(request, slug):
    current_hospital = get_current_hospital(request)
    doctor_qs = Doctor.objects.filter(slug=slug)
    if current_hospital:
        doctor_qs = doctor_qs.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True))
    doctor = get_object_or_404(doctor_qs)
    return render(request, "doctor/doctor_profile.html", {"doctor": doctor})


def specialist_doctors(request, id):
    current_hospital = get_current_hospital(request)
    specialist_qs = Specialist.objects.filter(id=id)
    if current_hospital:
        specialist_qs = specialist_qs.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True))
    specialist = get_object_or_404(specialist_qs)
    doctors = Doctor.objects.filter(specialist=specialist)
    if current_hospital:
        doctors = doctors.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True))

    return render(request, "doctors.html", {
        "specialist": specialist,
        "doctors": doctors
    })


# ================= BOOK APPOINTMENT =================
@login_required(login_url='login')
def book_appointment(request, slug):
    current_hospital = get_current_hospital(request)
    doctor_qs = Doctor.objects.filter(slug=slug)
    if current_hospital:
        doctor_qs = doctor_qs.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True))
    doctor = get_object_or_404(doctor_qs)

    if request.method == "POST":
        try:
            full_name = request.POST.get("name")
            email = (request.POST.get("email") or "").strip()
            phone = (request.POST.get("phone") or "").strip()
            date_str = request.POST.get("date")
            time_str = request.POST.get("time")
            message = request.POST.get("message")

            if not all([full_name, email, phone, date_str, time_str]):
                return JsonResponse({'success': False, 'message': 'Saari fields bharna zaroori hai.'})

            if not is_valid_email_address(email):
                return JsonResponse({'success': False, 'message': 'Please enter a valid email address.'})

            if not is_valid_indian_phone(phone):
                return JsonResponse({'success': False, 'message': 'Phone number must be exactly 10 digits.'})

            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            selected_time = datetime.strptime(time_str, "%H:%M").time()

            now_local = timezone.localtime(timezone.now())
            current_date = now_local.date()
            current_time = now_local.time()

            start_limit = time(9, 0)
            end_limit = time(17, 0)

            if not (start_limit <= selected_time < end_limit):
                return JsonResponse({'success': False, 'message': 'Clinic 9 AM se 5 PM tak khula hai.'})

            if selected_date < current_date:
                return JsonResponse({'success': False, 'message': 'Past date allowed nahi hai.'})

            if selected_date == current_date and selected_time <= current_time:
                return JsonResponse({'success': False, 'message': 'Past time allowed nahi hai.'})

            if selected_time.minute not in [0, 30]:
                return JsonResponse({'success': False, 'message': 'Sirf 30-minute slots allowed hain.'})

            if Appointment.objects.filter(
                doctor=doctor,
                date=selected_date,
                time=selected_time
            ).exclude(status="Cancelled").exists():
                return JsonResponse({'success': False, 'message': 'Ye slot already booked hai.'})

            fees = doctor.fees if doctor.fees else 500
            amount_in_paise = int(fees) * 100

            appointment = Appointment.objects.create(
                user=request.user,
                hospital=current_hospital or doctor.hospital,
                doctor=doctor,
                name=full_name,
                email=email,
                phone=phone,
                date=selected_date,
                time=selected_time,
                message=message,
                status="Pending"
            )

            notify_appointment_booked(appointment)

            try:
                order = client.order.create({
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "payment_capture": 1
                })

                return JsonResponse({
                    'success': True,
                    'pay_required': True,
                    'order_id': order['id'],
                    'amount': order['amount'],
                    'razorpay_key': settings.RAZORPAY_KEY_ID,
                    'appointment_id': appointment.id
                })
            except Exception:
                fallback_url = reverse('successful_payment') + f"?doctor_id={doctor.id}&appointment_id={appointment.id}"
                return JsonResponse({
                    'success': True,
                    'pay_required': False,
                    'appointment_id': appointment.id,
                    'redirect_url': fallback_url,
                    'message': 'Appointment booked. Payment gateway unavailable, so appointment is kept pending.'
                })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Server Error: {str(e)}'})

    patient = Patient.objects.filter(user=request.user).first()
    return render(request, "book_appointment.html", {
        "doctor": doctor,
        "patient": patient,
    })

def edit_appointment(request, id):
    appointment = get_object_or_404(Appointment, id=id, user=request.user)

    if request.method == "POST":
        try:
            date_str = request.POST.get("date")
            time_str = request.POST.get("time")

            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            selected_time = datetime.strptime(time_str, "%H:%M").time()

            now_local = timezone.localtime(timezone.now())
            current_date = now_local.date()
            current_time = now_local.time()

            start_limit = time(9, 0)
            end_limit = time(17, 0)

            if not (start_limit <= selected_time < end_limit):
                messages.error(request, "Clinic 9 AM se 5 PM tak khula hai.")
                return redirect('my_appointments')

            if selected_time.minute not in [0, 30]:
                messages.error(request, "Sirf 30-minute slots allowed hain.")
                return redirect('my_appointments')

            if selected_date < current_date or (selected_date == current_date and selected_time <= current_time):
                messages.error(request, "Past date/time allowed nahi hai.")
                return redirect('my_appointments')

            if Appointment.objects.filter(
                doctor=appointment.doctor,
                date=selected_date,
                time=selected_time
            ).exclude(id=appointment.id).exclude(status="Cancelled").exists():
                messages.error(request, "Ye slot already booked hai.")
                return redirect('my_appointments')

            appointment.date = selected_date
            appointment.time = selected_time
            appointment.status = "Pending"
            appointment.save()

            messages.success(request, "Appointment updated successfully. Payment dobara karna padega.")
            return redirect('my_appointments')

        except Exception as e:
            messages.error(request, f"Server Error: {str(e)}")
            return redirect('my_appointments')

    return render(request, "patient/edit_appointment.html", {"appointment": appointment})


@login_required(login_url='login')
def get_booked_slots(request):
    doctor_id = request.GET.get("doctor_id")
    date_str = request.GET.get("date")
    current_appointment_id = request.GET.get("appointment_id")

    if not doctor_id or not date_str:
        return JsonResponse({"success": False, "booked_slots": []})

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "booked_slots": []})

    booked_qs = Appointment.objects.filter(
        doctor_id=doctor_id,
        date=selected_date
    ).exclude(status="Cancelled")

    if current_appointment_id:
        booked_qs = booked_qs.exclude(id=current_appointment_id)

    booked_slots = [a.time.strftime("%H:%M") for a in booked_qs]
    return JsonResponse({"success": True, "booked_slots": booked_slots})


@login_required(login_url='login')
@require_POST
def cancel_appointment(request, id):
    appointment = get_object_or_404(Appointment, id=id, user=request.user)

    if appointment.status in ("Cancelled", "Completed"):
        messages.warning(request, "This appointment cannot be cancelled.")
        return redirect('my_appointments')

    appointment.status = "Cancelled"
    appointment.save(update_fields=['status'])
    notify_appointment_cancelled(appointment, cancelled_by="patient")
    log_activity(
        actor=request.user,
        action="appointment_cancelled",
        target_type="appointment",
        target_id=str(appointment.id),
        description="Patient cancelled appointment",
        extra_data={"doctor_id": appointment.doctor_id},
    )
    messages.success(request, "Appointment cancelled successfully")
    return redirect('my_appointments')


# ================= PAYMENT =================
@login_required(login_url='login')
def payment(request, id):
    doctor = get_object_or_404(Doctor, id=id)

    appointment_id = request.GET.get("appointment_id") or request.POST.get("appointment_id")

    if appointment_id:
        appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    else:
        appointment = Appointment.objects.filter(
            doctor=doctor,
            user=request.user
        ).order_by('-created_at').first()

    fees = doctor.fees if doctor.fees else 500

    order = client.order.create({
        "amount": int(fees) * 100,
        "currency": "INR",
        "payment_capture": 1
    })

    return render(request, "payment.html", {
        "doctor": doctor,
        "order_id": order["id"],
        "amount": order["amount"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "appointment_id": appointment.id if appointment else None
    })


# ================= PAYMENT SUCCESS =================
@login_required(login_url='login')
def successfull_payment(request):
    payment_id = request.GET.get("payment_id")
    order_id = request.GET.get("order_id")
    doctor_id = request.GET.get("doctor_id")
    appointment_id = request.GET.get("appointment_id")

    doctor = get_object_or_404(Doctor, id=doctor_id)

    appointment = None
    if appointment_id and appointment_id != 'None':
        appointment = Appointment.objects.filter(
            id=appointment_id,
            user=request.user
        ).first()

    if not appointment:
        appointment = Appointment.objects.filter(
            doctor=doctor,
            user=request.user
        ).order_by('-created_at').first()

    if not appointment:
        messages.error(request, "Appointment not found")
        return redirect("patient_dashboard")

    # Payment successful hone par appointment pending rahega.
    # Doctor dashboard se doctor khud Confirm/Complete karega.
    appointment.status = "Pending"
    appointment.save()

    if payment_id:
        Payment.objects.get_or_create(
            payment_id=payment_id,
            defaults={
                'appointment': appointment,
                'order_id': order_id,
                'amount': doctor.fees if doctor.fees else 500,
                'status': True
            }
        )

    patient = Patient.objects.filter(user=request.user).first()
    messages.success(request, "Appointment booked successfully.")
    if not is_patient_profile_complete(patient):
        messages.warning(request, "Please complete your profile details for faster future bookings.")
    return redirect("patient_dashboard")


# ================= PATIENT =================
@login_required(login_url='login')
def patient_dashboard(request):
    current_hospital = get_current_hospital(request)
    patient, _ = Patient.objects.get_or_create(
        user=request.user,
        defaults={
            "name": request.user.first_name or request.user.username,
            "email": request.user.email,
            "hospital": current_hospital,
        }
    )
    if current_hospital and not patient.hospital:
        patient.hospital = current_hospital
        patient.save(update_fields=["hospital"])

    appointments = Appointment.objects.filter(user=request.user).select_related("doctor", "hospital").order_by('-date', '-time')
    if current_hospital:
        appointments = appointments.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True)).order_by('-date', '-time')

    return render(request, "patient/patient_dashboard.html", {
        "patient": patient,
        "appointments": appointments,
        "profile_complete": is_patient_profile_complete(patient),
    })


@login_required(login_url='login')
def patient_profile(request):
    current_hospital = get_current_hospital(request)
    patient, _ = Patient.objects.get_or_create(
        user=request.user,
        defaults={
            "name": request.user.first_name or request.user.username,
            "email": request.user.email,
            "hospital": current_hospital,
        }
    )

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        phone = (request.POST.get("phone") or "").strip()
        address = (request.POST.get("address") or "").strip()
        age = (request.POST.get("age") or "").strip()
        date_of_birth = request.POST.get("date_of_birth")
        gender = request.POST.get("gender")
        profile_pic = request.FILES.get("profile_pic")

        if not full_name:
            messages.error(request, "Full name is required")
            return redirect("patient_profile")

        if email and not is_valid_email_address(email):
            messages.error(request, "Please enter a valid email address")
            return redirect("patient_profile")

        if phone and not re.fullmatch(r"\d{10,15}", phone):
            messages.error(request, "Phone number should be 10 to 15 digits")
            return redirect("patient_profile")

        age_value = None
        if age:
            try:
                age_value = int(age)
                if age_value <= 0 or age_value > 130:
                    raise ValueError
            except ValueError:
                messages.error(request, "Please enter a valid age")
                return redirect("patient_profile")

        name_parts = full_name.split(" ", 1)
        request.user.first_name = name_parts[0]
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ""
        request.user.email = email
        request.user.save()

        patient.name = full_name
        patient.email = email
        patient.hospital = patient.hospital or current_hospital
        patient.phone = phone or None
        patient.address = address or None
        patient.age = age_value
        patient.date_of_birth = date_of_birth or None
        patient.gender = gender or None
        if profile_pic:
            patient.profile_pic = profile_pic
        patient.save()

        messages.success(request, "Profile updated successfully")
        return redirect("patient_profile")

    return render(request, "patient/patient_profile.html", {
        "user": request.user,
        "patient": patient,
    })


@login_required(login_url='login')
def my_appointments(request):
    current_hospital = get_current_hospital(request)
    appointments = Appointment.objects.filter(
        user=request.user
    ).order_by('-date', '-time')
    if current_hospital:
        appointments = appointments.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True)).order_by('-date', '-time')
    return render(request, "patient/my_appointments.html", {
        "appointments": appointments
    })


@login_required(login_url='login')
def download_appointment_slip(request, id):
    appointment = get_object_or_404(Appointment.objects.select_related("doctor", "hospital"), id=id, user=request.user)
    payment = Payment.objects.filter(appointment=appointment, status=True).order_by("-created_at").first()
    amount = payment.amount if payment else (appointment.doctor.fees or 500)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Background card
    pdf.setFillColor(colors.HexColor("#f3f7fc"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    card_x = 28
    card_y = 34
    card_w = width - 56
    card_h = height - 68

    pdf.setFillColor(colors.white)
    pdf.roundRect(card_x, card_y, card_w, card_h, 14, fill=1, stroke=0)

    # Top header
    header_h = 92
    pdf.setFillColor(colors.HexColor("#165a9a"))
    pdf.roundRect(card_x, height - card_y - header_h, card_w, header_h, 14, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(card_x + 18, height - card_y - 35, "MEDICARE")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(card_x + 18, height - card_y - 52, "Compassionate Care, Trusted Excellence")

    generated_text = timezone.localtime(timezone.now()).strftime("%d %b %Y, %I:%M %p")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(card_x + card_w - 16, height - card_y - 30, "SLIP GENERATED")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(card_x + card_w - 16, height - card_y - 48, generated_text)

    # Title
    y = height - card_y - header_h - 34
    pdf.setFillColor(colors.HexColor("#1c2f47"))
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(card_x + card_w / 2, y, "APPOINTMENT SLIP")

    # Summary row
    y -= 42
    summary_h = 66
    summary_w = card_w - 28
    summary_x = card_x + 14
    pdf.setFillColor(colors.HexColor("#eef3f9"))
    pdf.roundRect(summary_x, y - summary_h, summary_w, summary_h, 8, fill=1, stroke=0)

    for i in range(1, 4):
        x = summary_x + (summary_w / 4) * i
        pdf.setStrokeColor(colors.HexColor("#d5dfec"))
        pdf.line(x, y - summary_h + 8, x, y - 8)

    status = (appointment.status or "Pending").strip()
    status_color = {
        "Pending": colors.HexColor("#f59e0b"),
        "Confirmed": colors.HexColor("#0ea5a8"),
        "Completed": colors.HexColor("#188a52"),
        "Cancelled": colors.HexColor("#dc2626"),
    }.get(status, colors.HexColor("#64748b"))

    blocks = [
        ("APPOINTMENT ID", str(appointment.id)),
        ("STATUS", status),
        ("DATE", appointment.date.strftime("%d %b %Y")),
        ("TIME", appointment.time.strftime("%I:%M %p")),
    ]

    for idx, (k, v) in enumerate(blocks):
        bx = summary_x + (summary_w / 4) * idx + (summary_w / 8)
        pdf.setFillColor(colors.HexColor("#35547a"))
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawCentredString(bx, y - 20, k)

        if k == "STATUS":
            pill_w = max(58, len(v) * 6.2 + 16)
            pill_x = bx - (pill_w / 2)
            pill_y = y - 46
            pdf.setFillColor(status_color)
            pdf.roundRect(pill_x, pill_y, pill_w, 18, 9, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawCentredString(bx, pill_y + 5, v)
        else:
            pdf.setFillColor(colors.HexColor("#1c2f47"))
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawCentredString(bx, y - 43, v)

    # Detail cards
    y -= (summary_h + 20)
    card_h2 = 132
    gap = 12
    col_w = (summary_w - gap) / 2

    def draw_detail_card(x, top_y, title, rows):
        pdf.setFillColor(colors.white)
        pdf.roundRect(x, top_y - card_h2, col_w, card_h2, 8, fill=1, stroke=0)
        pdf.setStrokeColor(colors.HexColor("#d8e2ef"))
        pdf.roundRect(x, top_y - card_h2, col_w, card_h2, 8, fill=0, stroke=1)
        pdf.setFillColor(colors.HexColor("#165a9a"))
        pdf.roundRect(x, top_y - 28, col_w, 28, 8, fill=1, stroke=0)
        pdf.rect(x, top_y - 28, col_w, 14, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(x + 10, top_y - 18, title)

        ry = top_y - 45
        for label, value in rows:
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(colors.HexColor("#6b7c93"))
            pdf.drawString(x + 10, ry, label)
            pdf.setFillColor(colors.HexColor("#1f3551"))
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawRightString(x + col_w - 10, ry, value[:38])
            ry -= 24

    draw_detail_card(
        summary_x,
        y,
        "PATIENT DETAILS",
        [
            ("Name", appointment.name or "N/A"),
            ("Phone", appointment.phone or "N/A"),
            ("Email", appointment.email or "N/A"),
        ],
    )

    draw_detail_card(
        summary_x + col_w + gap,
        y,
        "DOCTOR & HOSPITAL DETAILS",
        [
            ("Doctor", f"Dr. {appointment.doctor.name}" if appointment.doctor else "N/A"),
            ("Specialist", appointment.doctor.specialist.name if appointment.doctor and appointment.doctor.specialist else "N/A"),
            ("Hospital", appointment.hospital.name if appointment.hospital else "N/A"),
        ],
    )

    # Payment section
    y -= (card_h2 + 16)
    pay_h = 95
    pdf.setFillColor(colors.HexColor("#eaf7ef"))
    pdf.roundRect(summary_x, y - pay_h, summary_w, pay_h, 8, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#c9e8d3"))
    pdf.roundRect(summary_x, y - pay_h, summary_w, pay_h, 8, fill=0, stroke=1)

    pdf.setFillColor(colors.HexColor("#1d7a48"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(summary_x + 10, y - 18, "PAYMENT DETAILS")

    inner_x = summary_x + 10
    inner_y = y - 80
    inner_w = summary_w - 20
    inner_h = 48
    pdf.setFillColor(colors.white)
    pdf.roundRect(inner_x, inner_y, inner_w, inner_h, 6, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#d7ecdf"))
    pdf.roundRect(inner_x, inner_y, inner_w, inner_h, 6, fill=0, stroke=1)

    for i in range(1, 3):
        x = inner_x + (inner_w / 3) * i
        pdf.setStrokeColor(colors.HexColor("#e4efe8"))
        pdf.line(x, inner_y + 8, x, inner_y + inner_h - 8)

    pay_cells = [
        ("Payment ID", payment.payment_id if payment else "N/A"),
        ("Order ID", payment.order_id if payment else "N/A"),
        ("Amount", f"INR {amount}"),
    ]
    for idx, (k, v) in enumerate(pay_cells):
        cx = inner_x + (inner_w / 3) * idx + 8
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(colors.HexColor("#6a7e74"))
        pdf.drawString(cx, inner_y + inner_h - 14, k.upper())
        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(colors.HexColor("#1f3a2d"))
        pdf.drawString(cx, inner_y + 13, str(v)[:30])

    # Footer
    footer_y = card_y + 16
    pdf.setFillColor(colors.HexColor("#165a9a"))
    pdf.roundRect(summary_x, footer_y, summary_w, 24, 6, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(summary_x + summary_w / 2, footer_y + 8, "Please carry this slip to the hospital. For any queries, contact support.")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="appointment-slip-{appointment.id}.pdf"'
    return response


# ================= AUTH =================
import random
import time as pytime

def register_view(request):
    if request.method == "POST":
        email = (request.POST.get('email') or '').strip().lower()

        if not is_valid_email_address(email):
            messages.error(request, "Please enter a valid email address")
            return redirect('register')

        existing_user = User.objects.filter(email=email).first()
        if existing_user and (
            existing_user.is_superuser
            or Doctor.objects.filter(user=existing_user).exists()
            or HospitalAdminProfile.objects.filter(user=existing_user, is_active=True).exists()
        ):
            messages.error(request, "This account uses staff login. Please sign in with username and password.")
            return redirect('login')

        otp = str(random.randint(100000, 999999))
        request.session['otp_email'] = email
        request.session['otp_code'] = otp
        request.session['otp_expiry'] = pytime.time() + 600  # 10 minutes
        request.session['otp_next'] = request.GET.get('next') or request.POST.get('next') or ''

        subject = "Your MediCare OTP Code"
        body = f"Hello,\n\nYour login OTP is: {otp}\n\nThis code expires in 10 minutes."
        send_email_notification(subject, body, [email])

        messages.success(request, f"OTP sent to email {email}")
        return redirect('verify_otp')

    return render(request, 'register.html', {'next': request.GET.get('next', '')})


def verify_otp_view(request):
    email = request.session.get('otp_email')
    if not email:
        messages.error(request, "Session expired. Please start again.")
        return redirect('register')

    if request.method == "POST":
        entered_otp = request.POST.get('otp', '').strip()
        expected_otp = request.session.get('otp_code')
        expiry = request.session.get('otp_expiry', 0)

        if pytime.time() > expiry:
            messages.error(request, "OTP expired. Please try again.")
            return redirect('register')

        if entered_otp == expected_otp:
            user = User.objects.filter(email=email).first()
            is_new_user = False

            if user and (
                user.is_superuser
                or Doctor.objects.filter(user=user).exists()
                or HospitalAdminProfile.objects.filter(user=user, is_active=True).exists()
            ):
                messages.error(request, "This account uses staff login. Please sign in with username and password.")
                return redirect('login')

            if not user:
                username = build_unique_username_from_email(email)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=email.split("@")[0],
                    is_active=True,
                )
                user.set_unusable_password()
                user.save(update_fields=["password"])
                is_new_user = True
            elif not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])

            current_hospital = get_current_hospital(request)
            patient, _ = Patient.objects.get_or_create(
                user=user,
                defaults={
                    "name": user.first_name or user.username,
                    "email": user.email,
                    "hospital": current_hospital,
                }
            )
            if current_hospital and not patient.hospital:
                patient.hospital = current_hospital
                patient.save(update_fields=["hospital"])

            login(request, user)

            next_url = request.session.get('otp_next', '')
            for key in ['otp_email', 'otp_code', 'otp_expiry', 'otp_next']:
                if key in request.session:
                    del request.session[key]

            if is_new_user:
                messages.success(request, "Account created successfully. You are now logged in.")
            else:
                messages.success(request, "Logged in successfully.")

            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('patient_dashboard')
        else:
            messages.error(request, "Invalid OTP.")
            return redirect('verify_otp')

    return render(request, 'verify_otp.html', {'email': email})


def complete_registration_view(request):
    messages.info(request, "Email OTP now signs you in directly. Please continue with OTP login.")
    return redirect('register')


def select_hospital(request, slug):
    hospital = get_object_or_404(Hospital, slug=slug, is_active=True)
    request.session["hospital_id"] = hospital.id
    messages.success(request, f"Hospital switched to {hospital.name}")
    return redirect("home")


def login_view(request):
    if request.method == "POST":
        if (request.POST.get('action') or '').strip() == 'otp':
            email = (request.POST.get('email') or '').strip().lower()
            if not is_valid_email_address(email):
                messages.error(request, "Please enter a valid email address")
                return redirect('login')

            existing_user = User.objects.filter(email=email).first()
            if existing_user and (
                existing_user.is_superuser
                or Doctor.objects.filter(user=existing_user).exists()
                or HospitalAdminProfile.objects.filter(user=existing_user, is_active=True).exists()
            ):
                messages.error(request, "This account uses staff login. Please sign in with username and password.")
                return redirect('login')

            otp = str(random.randint(100000, 999999))
            request.session['otp_email'] = email
            request.session['otp_code'] = otp
            request.session['otp_expiry'] = pytime.time() + 600
            request.session['otp_next'] = request.POST.get('next') or request.GET.get('next') or ''

            subject = "Your MediCare OTP Code"
            body = f"Hello,\n\nYour login OTP is: {otp}\n\nThis code expires in 10 minutes."
            send_email_notification(subject, body, [email])

            messages.success(request, f"OTP sent to email {email}")
            return redirect('verify_otp')

        username = request.POST.get('username')
        password = request.POST.get('password')

        if is_login_locked(request, username):
            messages.error(request, "Too many failed login attempts. Try again after 15 minutes.")
            return redirect('login')

        user = authenticate(request, username=username, password=password)

        if user:
            clear_login_failures(request, username)
            login(request, user)

            admin_profile = HospitalAdminProfile.objects.filter(
                user=user,
                is_active=True,
            ).select_related('hospital').first()

            if user.is_superuser:
                return redirect('admin-dashboard')
            elif admin_profile:
                request.session["hospital_id"] = admin_profile.hospital_id
                return redirect('admin-dashboard')
            elif Doctor.objects.filter(user=user).exists():
                doctor_profile = Doctor.objects.filter(user=user).only('hospital_id').first()
                if doctor_profile and doctor_profile.hospital_id:
                    request.session["hospital_id"] = doctor_profile.hospital_id
                return redirect('doctor_dashboard')
            else:
                # Regular user / Patient
                return redirect('patient_dashboard')

        existing_user = User.objects.filter(username=username).first()
        if existing_user and not existing_user.is_active and existing_user.check_password(password):
            messages.error(request, "Please verify your email before login.")
            return redirect('login')

        register_login_failure(request, username)

        messages.error(request, "Invalid credentials")
        return redirect('login')

    return render(request, "login.html", {
        "next": request.GET.get("next", ""),
    })


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully")
    return redirect('home')


# ================= EXTRA =================
def about(request):
    return render(request, "extra/about.html")


def contact(request):
    if request.method == "POST":
        messages.success(request, "Message sent successfully")
    return render(request, "extra/contact.html")




@login_required(login_url='login')
def complete_profile_view(request):
    patient, _ = Patient.objects.get_or_create(
        user=request.user,
        defaults={
            "name": request.user.first_name or request.user.username,
            "email": request.user.email,
        }
    )
    
    if request.method == "POST":
        phone = (request.POST.get("phone") or "").strip()
        address = (request.POST.get("address") or "").strip()
        age = (request.POST.get("age") or "").strip()
        gender = request.POST.get("gender")
        
        if not all([phone, address, age, gender]):
            messages.error(request, "All fields are required to complete profile.")
            return render(request, "complete_profile.html", {"patient": patient})
            
        if phone and not re.fullmatch(r"\d{10,15}", phone):
            messages.error(request, "Phone number should be 10 to 15 digits.")
            return render(request, "complete_profile.html", {"patient": patient})
            
        try:
            age_value = int(age)
            if age_value <= 0 or age_value > 130:
                raise ValueError
        except ValueError:
            messages.error(request, "Please enter a valid age.")
            return render(request, "complete_profile.html", {"patient": patient})
            
        patient.phone = phone
        patient.address = address
        patient.age = age_value
        patient.gender = gender
        patient.save()
        
        messages.success(request, "Profile complete. Welcome to your dashboard!")
        return redirect('patient_dashboard')
        
    return render(request, "complete_profile.html", {"patient": patient})

from django.core.mail import send_mail, EmailMessage

def send_email_view(request):
    try:
        send_mail(
            'Hello User',
            'Welcome to my Django app',
            settings.DEFAULT_FROM_EMAIL,
            ['user@gmail.com'],
            fail_silently=False,
        )
        return HttpResponse("Email Sent ✅")
    except Exception as e:
        return HttpResponse(f"Error sending email: {str(e)}", status=500)


def send_html_email_view(request):
    try:
        email = EmailMessage(
            'Subject',
            '<h1>Hello</h1><p>This is HTML email</p>',
            settings.DEFAULT_FROM_EMAIL,
            ['user@gmail.com'],
        )
        email.content_subtype = 'html'
        email.send(fail_silently=False)
        return HttpResponse("HTML Email Sent ✅")
    except Exception as e:
        return HttpResponse(f"Error sending HTML email: {str(e)}", status=500)