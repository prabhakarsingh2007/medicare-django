from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db import IntegrityError
from django.utils.text import slugify
from django.db.models.functions import TruncMonth
from datetime import timedelta, date as date_cls, datetime as dt_cls

from doctors.models import Doctor
from accounts.models import Patient, HospitalAdminProfile
from appointments.models import Appointment
from core.models import Specialist, Hospital
from payments.models import Payment
from core.security_utils import is_strong_password, PASSWORD_RULE_TEXT
from core.activity import log_activity
from core.forms import HospitalForm, SpecialistForm
from doctors.forms import DoctorForm
from accounts.forms import HospitalAdminProfileForm


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

    # Optimized Monthly Trend query using TruncMonth
    monthly_trend = (
        appointment_qs
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    monthly_labels = []
    monthly_counts = []
    for item in monthly_trend:
        month_val = item['month']
        if not month_val:
            continue
        if isinstance(month_val, str):
            try:
                parsed_dt = dt_cls.fromisoformat(month_val)
                month_label = parsed_dt.strftime('%b %Y')
            except ValueError:
                month_label = month_val
        else:
            month_label = month_val.strftime('%b %Y')
        monthly_labels.append(month_label)
        monthly_counts.append(item['count'])

    # Optimized Daily Trend query (query last 14 days and aggregate in DB)
    trend_start = today - timedelta(days=13)
    daily_trend = (
        appointment_qs
        .filter(date__range=[trend_start, today])
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    daily_map = {}
    for item in daily_trend:
        d_val = item['date']
        if isinstance(d_val, str):
            try:
                d_val = date_cls.fromisoformat(d_val)
            except ValueError:
                pass
        daily_map[d_val] = item['count']

    daily_labels = []
    daily_counts = []
    for i in range(14):
        current_day = trend_start + timedelta(days=i)
        daily_labels.append(current_day.strftime('%d %b'))
        daily_counts.append(daily_map.get(current_day, 0))

    doctor_patient_summary = (
        appointment_qs
        .values('doctor__name')
        .annotate(patient_count=Count('email', distinct=True))
        .order_by('-patient_count', 'doctor__name')[:10]
    )
    doctor_labels = [item['doctor__name'] for item in doctor_patient_summary]
    doctor_patient_counts = [item['patient_count'] for item in doctor_patient_summary]

    super_dashboard = None
    if request.user.is_superuser:
        hospitals_overview = (
            Hospital.objects.filter(is_active=True)
            .annotate(
                doctor_total=Count('doctors', distinct=True),
                patient_total=Count('patients', distinct=True),
                appointment_total=Count('appointments', distinct=True),
                active_admin_total=Count('admin_profiles', filter=Q(admin_profiles__is_active=True), distinct=True),
            )
            .order_by('name')
        )

        revenue_rows = (
            Payment.objects.filter(status=True, appointment__hospital__isnull=False)
            .values('appointment__hospital')
            .annotate(total_revenue=Sum('amount'))
        )
        revenue_map = {item['appointment__hospital']: item['total_revenue'] or 0 for item in revenue_rows}

        overview_rows = []
        for hospital in hospitals_overview:
            overview_rows.append({
                'name': hospital.name,
                'doctor_total': hospital.doctor_total,
                'patient_total': hospital.patient_total,
                'appointment_total': hospital.appointment_total,
                'active_admin_total': hospital.active_admin_total,
                'revenue_total': revenue_map.get(hospital.id, 0),
            })

        total_revenue = sum(row['revenue_total'] for row in overview_rows)
        total_hospitals = len(overview_rows)
        total_usage = sum(row['appointment_total'] for row in overview_rows)
        avg_usage_per_hospital = round((total_usage / total_hospitals), 2) if total_hospitals else 0
        top_hospital = max(overview_rows, key=lambda row: row['appointment_total']) if overview_rows else None

        last_30_days = timezone.now() - timedelta(days=30)
        active_users_total = User.objects.filter(is_active=True).count()
        active_users_30d = User.objects.filter(is_active=True, last_login__gte=last_30_days).count()

        super_dashboard = {
            'overview_rows': overview_rows,
            'total_revenue': total_revenue,
            'total_usage': total_usage,
            'avg_usage_per_hospital': avg_usage_per_hospital,
            'top_hospital_name': top_hospital['name'] if top_hospital else '-',
            'top_hospital_usage': top_hospital['appointment_total'] if top_hospital else 0,
            'active_users_total': active_users_total,
            'active_users_30d': active_users_30d,
            'active_hospital_admins': HospitalAdminProfile.objects.filter(is_active=True, user__is_active=True).count(),
            'active_doctors': Doctor.objects.filter(user__is_active=True).count(),
            'active_patients': Patient.objects.filter(user__is_active=True).count(),
        }

    context = {
        "hospital_count": Hospital.objects.count() if request.user.is_superuser else (1 if admin_hospital else 0),
        "doctor_count": doctor_qs.count(),
        "patient_count": patient_qs.count(),
        "appointment_count": appointment_qs.count(),
        "today_count": appointment_qs.filter(date=today).count(),
        "recent_appointments": appointment_qs.order_by('-id')[:5],
        "today_date": today,
        "current_admin_hospital": admin_hospital,
        "monthly_labels": monthly_labels,
        "monthly_counts": monthly_counts,
        "daily_labels": daily_labels,
        "daily_counts": daily_counts,
        "doctor_labels": doctor_labels,
        "doctor_patient_counts": doctor_patient_counts,
        "super_dashboard": super_dashboard,
    }
    return render(request, "dashboard/dashboard.html", context)


@hospital_admin_required
def view_doctor(request):
    admin_hospital = get_admin_hospital(request)
    hospitals = Hospital.objects.filter(is_active=True).order_by('name')
    if admin_hospital:
        hospitals = hospitals.filter(id=admin_hospital.id)

    doctors = Doctor.objects.all().select_related('specialist', 'hospital').order_by('specialist__name', 'name')
    if admin_hospital:
        doctors = doctors.filter(hospital=admin_hospital)

    search_query = request.GET.get('search', '')
    hospital_id = request.GET.get('hospital', '')
    
    if search_query:
        doctors = doctors.filter(name__icontains=search_query)

    if hospital_id and request.user.is_superuser:
        doctors = doctors.filter(hospital_id=hospital_id)

    context = {
        "doctors": doctors,
        "search_query": search_query,
        "hospitals": hospitals,
        "selected_hospital": hospital_id,
        "current_admin_hospital": admin_hospital,
    }
    return render(request, "dashboard/view_doctor.html", context)


@hospital_admin_required
def add_doctor(request):
    admin_hospital = get_admin_hospital(request)
    hospitals = Hospital.objects.filter(is_active=True).order_by('name')
    specialists = Specialist.objects.all().order_by('name')

    if admin_hospital:
        hospitals = hospitals.filter(id=admin_hospital.id)
        specialists = specialists.filter(hospital=admin_hospital)

    if request.method == "POST":
        post_data = request.POST.copy()
        if admin_hospital:
            post_data['hospital'] = admin_hospital.id

        form = DoctorForm(post_data, request.FILES)
        if form.is_valid():
            try:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['name']
                )
                user.is_staff = True
                user.save()

                doctor = form.save(commit=False)
                doctor.user = user
                doctor.save()

                log_activity(
                    actor=request.user,
                    action="doctor_created",
                    target_type="doctor",
                    target_id=user.username,
                    description=f"Doctor account created for {doctor.name}",
                    extra_data={"hospital_id": doctor.hospital.id if doctor.hospital else None, "specialist_id": doctor.specialist.id},
                )

                messages.success(request, "Doctor added successfully!")
                return redirect("view_doctor")
            except Exception as exc:
                messages.error(request, f"Unable to add doctor: {exc}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = DoctorForm()

    return render(request, "dashboard/add_doctor.html", {
        "form": form,
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
    doctor_name = doctor.name
    doctor_id = doctor.id
    doctor.delete()
    log_activity(
        actor=request.user,
        action="doctor_deleted",
        target_type="doctor",
        target_id=str(doctor_id),
        description=f"Doctor deleted: {doctor_name}",
    )
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
        doctor.name = request.POST.get('name')
        doctor.experience = request.POST.get('experience')
        
        if request.FILES.get('image'):
            doctor.image = request.FILES.get('image')
        
        doctor.save()
        log_activity(
            actor=request.user,
            action="doctor_updated",
            target_type="doctor",
            target_id=str(doctor.id),
            description=f"Doctor updated: {doctor.name}",
            extra_data={"experience": doctor.experience},
        )
        return redirect('view_doctor')

    return render(request, 'dashboard/edit_doctor.html', {'doctor': doctor})


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

    return render(request, "dashboard/view_patient.html", context)


@hospital_admin_required
def view_appointment(request):
    appointments = Appointment.objects.all().select_related('doctor', 'hospital').order_by('-date', 'time')
    admin_hospital = get_admin_hospital(request)
    if admin_hospital:
        appointments = appointments.filter(hospital=admin_hospital)

    status_filter = request.GET.get('status_filter', 'active')
    if status_filter == 'cancelled':
        appointments = appointments.filter(status='Cancelled')
    elif status_filter == 'all':
        pass
    else:
        appointments = appointments.exclude(status='Cancelled')

    search_query = request.GET.get('search', '')
    if search_query:
        appointments = appointments.filter(
            Q(name__icontains=search_query) | 
            Q(doctor__name__icontains=search_query)
        )

    date_filter = request.GET.get('date_filter', '')
    if date_filter:
        appointments = appointments.filter(date=date_filter)

    return render(request, "dashboard/view_appoiment.html", {
        "appointments": appointments,
        "search_query": search_query,
        "date_filter": date_filter,
        "status_filter": status_filter
    })


@hospital_admin_required
def add_specialist(request):
    admin_hospital = get_admin_hospital(request)
    hospitals = Hospital.objects.filter(is_active=True).order_by('name')
    if admin_hospital:
        hospitals = hospitals.filter(id=admin_hospital.id)

    if request.method == "POST":
        form = SpecialistForm(request.POST, request.FILES)
        if form.is_valid():
            specialist = form.save()
            log_activity(
                actor=request.user,
                action="specialist_created",
                target_type="specialist",
                target_id=specialist.name,
                description=f"Specialist created: {specialist.name}",
                extra_data={"hospital_id": specialist.hospital.id} if specialist.hospital else {},
            )
            messages.success(request, "Specialist Added Successfully")
            return redirect("view_specialist")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = SpecialistForm()

    return render(request, "dashboard/add_specialist.html", {
        "form": form,
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

    return render(request, "dashboard/view_specialist.html", {
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
    specialist_name = specialist.name
    specialist_id = specialist.id
    specialist.delete()
    log_activity(
        actor=request.user,
        action="specialist_deleted",
        target_type="specialist",
        target_id=str(specialist_id),
        description=f"Specialist deleted: {specialist_name}",
    )
    messages.success(request, "Specialist deleted successfully!")
    return redirect('view_specialist')


@hospital_admin_required
def view_hospital(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can manage hospitals")
        return redirect("admin-dashboard")
    hospitals = Hospital.objects.all().order_by('name')
    return render(request, "dashboard/view_hospital.html", {"hospitals": hospitals})


@hospital_admin_required
def add_hospital(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can add hospitals")
        return redirect("admin-dashboard")

    if request.method == "POST":
        form = HospitalForm(request.POST)
        if form.is_valid():
            hospital = form.save(commit=False)
            hospital.is_active = True
            hospital.save()
            log_activity(
                actor=request.user,
                action="hospital_created",
                target_type="hospital",
                target_id=str(hospital.id),
                description=f"Hospital created: {hospital.name}",
            )
            messages.success(request, "Hospital added successfully")
            return redirect("view_hospital")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = HospitalForm()

    return render(request, "dashboard/add_hospital.html", {"form": form})


@hospital_admin_required
def delete_hospital(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can delete hospitals")
        return redirect("admin-dashboard")

    hospital = get_object_or_404(Hospital, pk=pk)
    hospital_name = hospital.name
    hospital_id = hospital.id
    hospital.delete()
    log_activity(
        actor=request.user,
        action="hospital_deleted",
        target_type="hospital",
        target_id=str(hospital_id),
        description=f"Hospital deleted: {hospital_name}",
    )
    messages.success(request, "Hospital deleted successfully")
    return redirect('view_hospital')


@hospital_admin_required
def edit_hospital(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can edit hospitals")
        return redirect("admin-dashboard")

    hospital = get_object_or_404(Hospital, pk=pk)

    if request.method == "POST":
        form = HospitalForm(request.POST, instance=hospital)
        if form.is_valid():
            form.save()
            log_activity(
                actor=request.user,
                action="hospital_updated",
                target_type="hospital",
                target_id=str(hospital.id),
                description=f"Hospital updated: {hospital.name}",
            )
            messages.success(request, "Hospital updated successfully")
            return redirect("view_hospital")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = HospitalForm(instance=hospital)

    return render(request, "dashboard/edit_hospital.html", {
        "form": form,
        "hospital": hospital,
    })


@hospital_admin_required
def toggle_hospital_status(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can toggle hospital status")
        return redirect("admin-dashboard")

    hospital = get_object_or_404(Hospital, pk=pk)
    hospital.is_active = not hospital.is_active
    hospital.save(update_fields=['is_active'])
    status_text = "activated" if hospital.is_active else "deactivated"
    log_activity(
        actor=request.user,
        action="hospital_status_changed",
        target_type="hospital",
        target_id=str(hospital.id),
        description=f"Hospital {status_text}: {hospital.name}",
    )
    messages.success(request, f"Hospital {status_text} successfully")
    return redirect('view_hospital')


@hospital_admin_required
def add_hospital_admin(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can create hospital admins")
        return redirect("admin-dashboard")

    hospitals = Hospital.objects.filter(is_active=True).order_by('name')

    if request.method == "POST":
        form = HospitalAdminProfileForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    email=form.cleaned_data['email'],
                    first_name=form.cleaned_data['full_name'],
                )
                user.is_staff = True
                user.save()

                profile = form.save(commit=False)
                profile.user = user
                profile.is_active = True
                profile.save()

                log_activity(
                    actor=request.user,
                    action="hospital_admin_created",
                    target_type="hospital_admin",
                    target_id=user.username,
                    description=f"Hospital admin created for {profile.hospital.name}",
                    extra_data={"hospital_id": profile.hospital.id},
                )
                messages.success(request, "Hospital admin created successfully")
                return redirect("view_hospital_admins")
            except Exception as exc:
                messages.error(request, f"Unable to create hospital admin: {exc}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = HospitalAdminProfileForm()

    return render(request, "dashboard/add_hospital_admin.html", {
        "form": form,
        "hospitals": hospitals,
    })


@hospital_admin_required
def view_hospital_admins(request):
    if not request.user.is_superuser:
        messages.error(request, "Only super admin can view hospital admins")
        return redirect("admin-dashboard")

    admins = HospitalAdminProfile.objects.select_related('user', 'hospital').order_by('hospital__name', 'user__username')
    return render(request, "dashboard/view_hospital_admins.html", {"admins": admins})


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
    log_activity(
        actor=request.user,
        action="hospital_admin_status_changed",
        target_type="hospital_admin",
        target_id=str(profile.id),
        description=f"Hospital admin {status_text}: {profile.user.username}",
        extra_data={"is_active": profile.is_active, "hospital_id": profile.hospital_id},
    )
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

        if not is_strong_password(new_password):
            messages.error(request, PASSWORD_RULE_TEXT)
            return redirect("reset_hospital_admin_password", pk=pk)

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("reset_hospital_admin_password", pk=pk)

        profile.user.set_password(new_password)
        profile.user.save(update_fields=['password'])
        log_activity(
            actor=request.user,
            action="hospital_admin_password_reset",
            target_type="hospital_admin",
            target_id=str(profile.id),
            description=f"Password reset for hospital admin: {profile.user.username}",
        )
        messages.success(request, "Hospital admin password reset successfully")
        return redirect("view_hospital_admins")

    return render(request, "dashboard/reset_hospital_admin_password.html", {"profile": profile})


@hospital_admin_required
def change_admin_password(request):
    # Only superadmin can change password — hospital admins are blocked
    if not request.user.is_superuser:
        messages.error(request, "You are not allowed to change your password. Contact the super admin.")
        return redirect("admin-dashboard")

    if request.method == "POST":
        current_password = request.POST.get("current_password") or ""
        new_password = request.POST.get("new_password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect")
            return redirect("change_admin_password")

        if not is_strong_password(new_password):
            messages.error(request, PASSWORD_RULE_TEXT)
            return redirect("change_admin_password")

        if new_password != confirm_password:
            messages.error(request, "New password and confirm password do not match")
            return redirect("change_admin_password")

        request.user.set_password(new_password)
        request.user.save(update_fields=['password'])
        update_session_auth_hash(request, request.user)

        log_activity(
            actor=request.user,
            action="admin_password_changed",
            target_type="user",
            target_id=str(request.user.id),
            description="Admin changed own password",
        )

        messages.success(request, "Password changed successfully")
        return redirect("admin-dashboard")

    return render(request, "dashboard/change_admin_password.html")
