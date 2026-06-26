from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from core.models import Specialist, Hospital
from doctors.models import Doctor


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
        return None

    return hospital


def home(request):
    current_hospital = get_current_hospital(request)

    try:
        specialists_qs = Specialist.objects.all()

        if current_hospital:
            specialists_qs = specialists_qs.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True))

        specialists = list(specialists_qs)
        hospitals = list(Hospital.objects.filter(is_active=True).order_by("name"))
    except (OperationalError, ProgrammingError):
        specialists = []
        hospitals = []
        current_hospital = None

    return render(request, "core/home.html", {
        "specialists": specialists,
        "hospitals": hospitals,
        "current_hospital": current_hospital,
    })


def select_hospital(request, slug):
    """Patient selects a hospital — saves in session, redirects to home."""
    try:
        hospital = get_object_or_404(Hospital, slug=slug, is_active=True)
        request.session["hospital_id"] = hospital.id
    except Exception:
        pass
    return redirect("home")


def hospital_detail(request, slug):
    """Public page for a single hospital — shows info, doctors, specialists."""
    hospital = get_object_or_404(Hospital, slug=slug, is_active=True)
    doctors = Doctor.objects.filter(hospital=hospital).select_related('specialist').order_by('specialist__name', 'name')
    specialists = Specialist.objects.filter(hospital=hospital).order_by('name')
    hospitals = list(Hospital.objects.filter(is_active=True).order_by("name"))

    return render(request, "core/hospital_detail.html", {
        "hospital": hospital,
        "doctors": doctors,
        "specialists": specialists,
        "hospitals": hospitals,
        "current_hospital": hospital,
    })


def about(request):
    return render(request, "core/about.html")


def contact(request):
    if request.method == "POST":
        from django.contrib import messages
        messages.success(request, "Message sent successfully")
    return render(request, "core/contact.html")
