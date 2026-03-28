
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils import timezone

from .models import (
    Doctor, Patient, Appointment, Specialist, Hospital, HospitalAdminProfile,
)


def is_hospital_admin_or_superuser(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return HospitalAdminProfile.objects.filter(user=user, is_active=True).exists()


hospital_admin_required = user_passes_test(is_hospital_admin_or_superuser, login_url='login')


def get_admin_hospital(request):
    if request.user.is_superuser:
        return None
    profile = HospitalAdminProfile.objects.filter(
        user=request.user,
        is_active=True,
    ).select_related('hospital').first()
    return profile.hospital if profile else None

# ================= ADMIN DASHBOARD =================
@hospital_admin_required
def dashboard(request):
    today = timezone.localtime(timezone.now()).date()
    admin_hospital = get_admin_hospital(request)

    doctor_qs = Doctor.objects.all()
    patient_qs = Patient.objects.all()
    appointment_qs = Appointment.objects.all()

    if admin_hospital:
        doctor_qs = doctor_qs.filter(hospital=admin_hospital)
        patient_qs = patient_qs.filter(hospital=admin_hospital)
        appointment_qs = appointment_qs.filter(hospital=admin_hospital)

    context = {
        "hospital_count": Hospital.objects.count() if request.user.is_superuser else (1 if admin_hospital else 0),
        "doctor_count": doctor_qs.count(),
        "patient_count": patient_qs.count(),
        "appointment_count": appointment_qs.count(),
        "today_count": appointment_qs.filter(date=today).count(),
        "recent_appointments": appointment_qs.order_by('-id')[:5],
        "today_date": today,
        "current_admin_hospital": admin_hospital,
    }
    return render(request, "admin/dashboard.html", context)


# ================= DOCTOR =================
@hospital_admin_required
def view_doctor(request):
    admin_hospital = get_admin_hospital(request)
    hospitals = Hospital.objects.filter(is_active=True).order_by('name')
    if admin_hospital:
        hospitals = hospitals.filter(id=admin_hospital.id)

    doctors = Doctor.objects.all().order_by('specialist__name', 'name')
    if admin_hospital:
        doctors = doctors.filter(hospital=admin_hospital)

    search_query = request.GET.get('search', '')
    hospital_id = request.GET.get('hospital', '')
    
    if search_query:
        doctors = doctors.filter(name__icontains=search_query)

    if hospital_id and request.user.is_superuser:
        doctors = doctors.filter(hospital_id=hospital_id)

    # 3. Data ko template par bhejna
    context = {
        "doctors": doctors,
        "search_query": search_query,
        "hospitals": hospitals,
        "selected_hospital": hospital_id,
        "current_admin_hospital": admin_hospital,
    }
    return render(request, "admin/view_doctor.html", context)
from django.utils.text import slugify

@hospital_admin_required
def add_doctor(request):
    admin_hospital = get_admin_hospital(request)
    hospitals = Hospital.objects.filter(is_active=True).order_by('name')
    specialists = Specialist.objects.all().order_by('name')

    if admin_hospital:
        hospitals = hospitals.filter(id=admin_hospital.id)
        specialists = specialists.filter(hospital=admin_hospital)

    if request.method == "POST":
        name = request.POST.get("name")
        photo = request.FILES.get("photo")
        qualification = request.POST.get("qualification")
        specialist_id = request.POST.get("specialist")
        experience = request.POST.get("experience")
        username = request.POST.get("username")
        password = request.POST.get("password")
        hospital_id = request.POST.get("hospital")

        if admin_hospital:
            hospital = admin_hospital
        elif not hospital_id:
            messages.error(request, "Please select hospital")
            return redirect("add_doctor")
        else:
            hospital = get_object_or_404(Hospital, id=hospital_id)

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("add_doctor")

        specialist = get_object_or_404(Specialist, id=specialist_id)
        if specialist.hospital_id and specialist.hospital_id != hospital.id:
            messages.error(request, "Selected specialist belongs to another hospital")
            return redirect("add_doctor")

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=name
        )
        user.is_staff = True
        user.save()

        # 👇 AUTO SLUG (user se nahi le rahe)
        slug = slugify(name)

        Doctor.objects.create(
            name=name,
            hospital=hospital,
            user=user,
            slug=slug,
            image=photo,
            qualification=qualification,
            specialist=specialist,
            experience=experience
        )

        messages.success(request, "Doctor added successfully!")
        return redirect("view_doctor")

    return render(request, "admin/add_doctor.html", {
        "specialists": specialists,
        "hospitals": hospitals,
        "allow_hospital_select": request.user.is_superuser,
        "current_admin_hospital": admin_hospital,
    })

@hospital_admin_required
def delete_doctor(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    admin_hospital = get_admin_hospital(request)
    if admin_hospital and doctor.hospital_id != admin_hospital.id:
        messages.error(request, "You can delete only your hospital doctors")
        return redirect('view_doctor')
    doctor.delete()
    messages.success(request, "Doctor deleted successfully!")
    return redirect('view_doctor')

@hospital_admin_required
def edit_doctor(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    admin_hospital = get_admin_hospital(request)
    if admin_hospital and doctor.hospital_id != admin_hospital.id:
        messages.error(request, "You can edit only your hospital doctors")
        return redirect('view_doctor')
    
    if request.method == 'POST':
        # Data Update Karne Ka Logic
        doctor.name = request.POST.get('name')
        doctor.phone = request.POST.get('phone')
        doctor.experience = request.POST.get('experience')
        
        if request.FILES.get('image'):
            doctor.image = request.FILES.get('image')
        
        doctor.save()
        return redirect('view_doctor') # POST ke baad return hona zaroori hai

    # --- YAHAN DHAYAN DEIN ---
    # GET request ke liye ye return hona MUST hai. 
    # Aapka error bata raha hai ki ye line miss ho gayi hai ya galat indented hai.
    return render(request, 'admin/edit_doctor.html', {'doctor': doctor})


# ================= PATIENT =================
@hospital_admin_required
def view_patient(request):
    today = timezone.localtime(timezone.now()).date()
    admin_hospital = get_admin_hospital(request)

    today_patients = Appointment.objects.filter(date=today).order_by('time')
    all_patients = Appointment.objects.all().order_by('-date')

    if admin_hospital:
        today_patients = today_patients.filter(hospital=admin_hospital)
        all_patients = all_patients.filter(hospital=admin_hospital)

    context = {
        "today_patients": today_patients,
        "all_patients": all_patients,
        "today_date": today,
    }

    try:
        return render(request, "admin/view_patient.html", context)
    except:
        return render(request, "admin/manage_patients.html", context)


# ================= APPOINTMENT =================
from django.db.models import Q

@hospital_admin_required
def view_appointment(request):
    # Base query
    appointments = Appointment.objects.all().order_by('-date', 'time')
    admin_hospital = get_admin_hospital(request)
    if admin_hospital:
        appointments = appointments.filter(hospital=admin_hospital)

    # 0. Status Filter Logic
    status_filter = request.GET.get('status_filter', 'active')
    if status_filter == 'cancelled':
        appointments = appointments.filter(status='Cancelled')
    elif status_filter == 'all':
        pass
    else:
        appointments = appointments.exclude(status='Cancelled')

    # 1. Search Logic (Search by Patient or Doctor Name)
    search_query = request.GET.get('search', '')
    if search_query:
        appointments = appointments.filter(
            Q(name__icontains=search_query) | 
            Q(doctor__name__icontains=search_query)
        )

    # 2. Date Filter Logic
    date_filter = request.GET.get('date_filter', '')
    if date_filter:
        appointments = appointments.filter(date=date_filter)

    return render(request, "admin/view_appoiment.html", {
        "appointments": appointments,
        "search_query": search_query,
        "date_filter": date_filter,
        "status_filter": status_filter
    })

# ================= SPECIALIST =================
@hospital_admin_required
def add_specialist(request):
    admin_hospital = get_admin_hospital(request)
    hospitals = Hospital.objects.filter(is_active=True).order_by('name')
    if admin_hospital:
        hospitals = hospitals.filter(id=admin_hospital.id)

    if request.method == "POST":
        name = request.POST.get("name")
        icon = request.FILES.get("icon")
        hospital_id = request.POST.get("hospital")

        if admin_hospital:
            hospital = admin_hospital
        elif not hospital_id:
            messages.error(request, "Please select hospital")
            return redirect("add_specialist")
        else:
            hospital = get_object_or_404(Hospital, id=hospital_id)

        Specialist.objects.create(
            hospital=hospital,
            name=name,
            icon=icon
        )

        messages.success(request, "Specialist Added Successfully")
        return redirect("view_specialist")

    return render(request, "admin/add_specialist.html", {
        "hospitals": hospitals,
        "allow_hospital_select": request.user.is_superuser,
        "current_admin_hospital": admin_hospital,
    })


@hospital_admin_required
def view_specialist(request):
    admin_hospital = get_admin_hospital(request)
    hospitals = Hospital.objects.filter(is_active=True).order_by('name')
    if admin_hospital:
        hospitals = hospitals.filter(id=admin_hospital.id)

    hospital_id = request.GET.get('hospital', '')

    specialists = Specialist.objects.all().order_by('name')
    if admin_hospital:
        specialists = specialists.filter(hospital=admin_hospital)
    elif hospital_id:
        specialists = specialists.filter(hospital_id=hospital_id)

    return render(request, "admin/view_specialist.html", {
        "specialists": specialists,
        "hospitals": hospitals,
        "selected_hospital": hospital_id,
        "current_admin_hospital": admin_hospital,
    })

@hospital_admin_required
def delete_specialist(request, pk):
    specialist = get_object_or_404(Specialist, pk=pk)
    admin_hospital = get_admin_hospital(request)
    if admin_hospital and specialist.hospital_id != admin_hospital.id:
        messages.error(request, "You can delete only your hospital specialists")
        return redirect('view_specialist')
    specialist.delete()
    messages.success(request, "Specialist deleted successfully!")
    return redirect('view_specialist')


# ================= HOSPITAL =================
@hospital_admin_required
def view_hospital(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can manage hospitals")
        return redirect("admin-dashboard")
    hospitals = Hospital.objects.all().order_by('name')
    return render(request, "admin/view_hospital.html", {"hospitals": hospitals})


@hospital_admin_required
def add_hospital(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can add hospitals")
        return redirect("admin-dashboard")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        address = (request.POST.get("address") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()

        if not name:
            messages.error(request, "Hospital name is required")
            return redirect("add_hospital")

        if Hospital.objects.filter(name__iexact=name).exists():
            messages.error(request, "Hospital already exists")
            return redirect("add_hospital")

        Hospital.objects.create(
            name=name,
            address=address or None,
            phone=phone or None,
            email=email or None,
            is_active=True,
        )
        messages.success(request, "Hospital added successfully")
        return redirect("view_hospital")

    return render(request, "admin/add_hospital.html")


@hospital_admin_required
def delete_hospital(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can delete hospitals")
        return redirect("admin-dashboard")

    hospital = get_object_or_404(Hospital, pk=pk)
    hospital.delete()
    messages.success(request, "Hospital deleted successfully")
    return redirect('view_hospital')


@hospital_admin_required
def add_hospital_admin(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can create hospital admins")
        return redirect("admin-dashboard")

    hospitals = Hospital.objects.filter(is_active=True).order_by('name')

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        email = (request.POST.get("email") or "").strip().lower()
        hospital_id = request.POST.get("hospital")

        if not all([full_name, username, password, hospital_id]):
            messages.error(request, "All required fields must be filled")
            return redirect("add_hospital_admin")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("add_hospital_admin")

        if email and User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("add_hospital_admin")

        hospital = get_object_or_404(Hospital, id=hospital_id)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=full_name,
        )
        user.is_staff = True
        user.save()

        HospitalAdminProfile.objects.create(user=user, hospital=hospital, is_active=True)
        messages.success(request, "Hospital admin created successfully")
        return redirect("view_hospital_admins")

    return render(request, "admin/add_hospital_admin.html", {"hospitals": hospitals})


@hospital_admin_required
def view_hospital_admins(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can view hospital admins")
        return redirect("admin-dashboard")

    admins = HospitalAdminProfile.objects.select_related('user', 'hospital').order_by('hospital__name', 'user__username')
    return render(request, "admin/view_hospital_admins.html", {"admins": admins})


@hospital_admin_required
def toggle_hospital_admin_status(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can manage hospital admins")
        return redirect("admin-dashboard")

    profile = get_object_or_404(HospitalAdminProfile, pk=pk)
    profile.is_active = not profile.is_active
    profile.save(update_fields=['is_active'])

    profile.user.is_active = profile.is_active
    profile.user.save(update_fields=['is_active'])

    status_text = "activated" if profile.is_active else "deactivated"
    messages.success(request, f"Hospital admin {status_text} successfully")
    return redirect("view_hospital_admins")


@hospital_admin_required
def reset_hospital_admin_password(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can reset hospital admin passwords")
        return redirect("admin-dashboard")

    profile = get_object_or_404(HospitalAdminProfile, pk=pk)

    if request.method == "POST":
        new_password = request.POST.get("new_password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        if len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return redirect("reset_hospital_admin_password", pk=pk)

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("reset_hospital_admin_password", pk=pk)

        profile.user.set_password(new_password)
        profile.user.save(update_fields=['password'])
        messages.success(request, "Hospital admin password reset successfully")
        return redirect("view_hospital_admins")

    return render(request, "admin/reset_hospital_admin_password.html", {"profile": profile})


@hospital_admin_required
def change_admin_password(request):
    if request.method == "POST":
        current_password = request.POST.get("current_password") or ""
        new_password = request.POST.get("new_password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect")
            return redirect("change_admin_password")

        if len(new_password) < 6:
            messages.error(request, "New password must be at least 6 characters")
            return redirect("change_admin_password")

        if new_password != confirm_password:
            messages.error(request, "New password and confirm password do not match")
            return redirect("change_admin_password")

        request.user.set_password(new_password)
        request.user.save(update_fields=['password'])
        update_session_auth_hash(request, request.user)

        messages.success(request, "Password changed successfully")
        return redirect("admin-dashboard")

    return render(request, "admin/change_admin_password.html")
