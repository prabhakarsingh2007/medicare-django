from django.shortcuts import render, redirect
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from core.models import Specialist, Hospital

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


def about(request):
    return render(request, "core/about.html")


def contact(request):
    if request.method == "POST":
        from django.contrib import messages
        messages.success(request, "Message sent successfully")
    return render(request, "core/contact.html")
