from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re

from datetime import datetime, timedelta, time

import razorpay

from .models import *


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


def is_strong_password(password):
    if not password or len(password) < 6:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True


def get_current_hospital(request):
    selected_slug = request.GET.get("hospital")
    hospital_id = request.session.get("hospital_id")
    hospital = None

    if selected_slug:
        hospital = Hospital.objects.filter(slug=selected_slug, is_active=True).first()
    elif hospital_id:
        hospital = Hospital.objects.filter(id=hospital_id, is_active=True).first()

    if not hospital:
        hospital = Hospital.objects.filter(is_active=True).order_by("name").first()

    if hospital:
        request.session["hospital_id"] = hospital.id

    return hospital


# ================= HOME =================
def home(request):
    current_hospital = get_current_hospital(request)
    specialists = Specialist.objects.all()

    if current_hospital:
        specialists = specialists.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True))

    hospitals = Hospital.objects.filter(is_active=True).order_by("name")

    return render(request, "home.html", {
        "specialists": specialists,
        "hospitals": hospitals,
        "current_hospital": current_hospital,
    })


# ================= DOCTOR =================
@login_required(login_url='login')
def doctor_dashboard(request):
    current_hospital = get_current_hospital(request)
    doctor = Doctor.objects.filter(user=request.user).first()
    if current_hospital:
        doctor = Doctor.objects.filter(
            user=request.user
        ).filter(Q(hospital=current_hospital) | Q(hospital__isnull=True)).first()
    appointments = Appointment.objects.none()

    if doctor:
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

            order = client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "payment_capture": 1
            })

            return JsonResponse({
                'success': True,
                'order_id': order['id'],
                'amount': order['amount'],
                'razorpay_key': settings.RAZORPAY_KEY_ID,
                'appointment_id': appointment.id
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Server Error: {str(e)}'})

    return render(request, "book_appointment.html", {"doctor": doctor})

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


def cancel_appointment(request, id):
    appointment = get_object_or_404(Appointment, id=id, user=request.user)
    appointment.status = "Cancelled"
    appointment.save()
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
        return render(request, "appointment_success.html", {
            "doctor": doctor,
            "error": "Appointment not found"
        })

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

    return render(request, "appointment_success.html", {
        "doctor": doctor,
        "appointment": appointment,
        "payment_id": payment_id,
        "date": appointment.date,
        "time": appointment.time
    })


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
    return render(request, "patient/patient_dashboard.html", {"patient": patient})


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


# ================= AUTH =================
def register_view(request):
    current_hospital = get_current_hospital(request)
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        email = (request.POST.get('email') or '').strip().lower()
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if not all([full_name, username, email, password1, password2]):
            messages.error(request, "All fields required")
            return redirect('register')

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect('register')

        if not is_strong_password(password1):
            messages.error(request, "Password must be at least 6 characters and include 1 uppercase letter, 1 number, and 1 special character")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('register')

        if not is_valid_email_address(email):
            messages.error(request, "Please enter a valid email address")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered")
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=full_name
        )

        Patient.objects.create(user=user, name=full_name, email=email, hospital=current_hospital)

        messages.success(request, "Account created successfully")
        return redirect('login')

    return render(request, 'register.html')


def select_hospital(request, slug):
    hospital = get_object_or_404(Hospital, slug=slug, is_active=True)
    request.session["hospital_id"] = hospital.id
    messages.success(request, f"Hospital switched to {hospital.name}")
    return redirect("home")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
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
                return redirect('doctor_dashboard')
            else:
                return redirect('home')

        messages.error(request, "Invalid credentials")
        return redirect('login')

    return render(request, "login.html")


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