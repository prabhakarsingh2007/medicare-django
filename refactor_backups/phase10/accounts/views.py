from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils.crypto import get_random_string
import re
import random
import time as pytime

from core.models import Hospital
from accounts.models import Patient, HospitalAdminProfile
from doctors.models import Doctor
from notifications.notifications import send_email_notification
from core.activity import log_activity
from core.views import get_current_hospital


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


def _otp_lock_key(request, email):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
    return f"otp-lock:{ip}:{(email or '').lower()}"


def is_otp_locked(request, email):
    lock_key = _otp_lock_key(request, email)
    attempts = cache.get(lock_key, 0)
    return attempts >= 5


def register_otp_failure(request, email):
    lock_key = _otp_lock_key(request, email)
    attempts = cache.get(lock_key, 0) + 1
    cache.set(lock_key, attempts, timeout=900)  # 15 minutes lockout


def clear_otp_failures(request, email):
    cache.delete(_otp_lock_key(request, email))


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

    return render(request, 'accounts/register.html', {'next': request.GET.get('next', '')})


def verify_otp_view(request):
    email = request.session.get('otp_email')
    if not email:
        messages.error(request, "Session expired. Please start again.")
        return redirect('register')

    if is_otp_locked(request, email):
        messages.error(request, "Too many failed OTP attempts. Try again after 15 minutes.")
        return redirect('register')

    if request.method == "POST":
        entered_otp = request.POST.get('otp', '').strip()
        expected_otp = request.session.get('otp_code')
        expiry = request.session.get('otp_expiry', 0)

        if pytime.time() > expiry:
            messages.error(request, "OTP expired. Please try again.")
            return redirect('register')

        if entered_otp == expected_otp:
            clear_otp_failures(request, email)
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
            register_otp_failure(request, email)
            if is_otp_locked(request, email):
                messages.error(request, "Too many failed OTP attempts. Try again after 15 minutes.")
                return redirect('register')
            
            attempts = cache.get(_otp_lock_key(request, email), 0)
            remaining = 5 - attempts
            messages.error(request, f"Invalid OTP. {remaining} attempts remaining.")
            return redirect('verify_otp')

    return render(request, 'accounts/verify_otp.html', {'email': email})


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
                return redirect('patient_dashboard')

        existing_user = User.objects.filter(username=username).first()
        if existing_user and not existing_user.is_active and existing_user.check_password(password):
            messages.error(request, "Please verify your email before login.")
            return redirect('login')

        register_login_failure(request, username)

        messages.error(request, "Invalid credentials")
        return redirect('login')

    return render(request, "accounts/login.html", {
        "next": request.GET.get("next", ""),
    })


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully")
    return redirect('home')


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

    return render(request, "accounts/patient_profile.html", {
        "user": request.user,
        "patient": patient,
    })


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
            return render(request, "accounts/complete_profile.html", {"patient": patient})
            
        if phone and not re.fullmatch(r"\d{10,15}", phone):
            messages.error(request, "Phone number should be 10 to 15 digits.")
            return render(request, "accounts/complete_profile.html", {"patient": patient})
            
        try:
            age_value = int(age)
            if age_value <= 0 or age_value > 130:
                raise ValueError
        except ValueError:
            messages.error(request, "Please enter a valid age.")
            return render(request, "accounts/complete_profile.html", {"patient": patient})
            
        patient.phone = phone
        patient.address = address
        patient.age = age_value
        patient.gender = gender
        patient.save()
        
        messages.success(request, "Profile complete. Welcome to your dashboard!")
        return redirect('patient_dashboard')
        
    return render(request, "accounts/complete_profile.html", {"patient": patient})
