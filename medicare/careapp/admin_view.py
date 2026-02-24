
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone

from .models import (
    Doctor, Patient, Appointment, Specialist,
    Ambulance, AmbulanceBooking,
    LabTest, LabBooking,
    Medicine, MedicineOrder
)

# ================= ADMIN DASHBOARD =================
@staff_member_required
def dashboard(request):
    today = timezone.localtime(timezone.now()).date()

    context = {
        "doctor_count": Doctor.objects.count(),
        "patient_count": Patient.objects.count(),
        "appointment_count": Appointment.objects.count(),
        "today_count": Appointment.objects.filter(date=today).count(),
        "recent_appointments": Appointment.objects.all().order_by('-id')[:5],
        "today_date": today,
    }
    return render(request, "admin/dashboard.html", context)


# ================= DOCTOR =================
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import Doctor # Ensure aapka model name yahi ho

@staff_member_required
def view_doctor(request):
    # 1. Sabse pehle saare doctors lein (ordered by specialist)
    doctors = Doctor.objects.all().order_by('specialist__name', 'name')

    # 2. Search Logic: URL se 'search' parameter ko uthana
    search_query = request.GET.get('search', '')
    
    if search_query:
        # Agar search box mein kuch likha hai, toh filter apply karein
        doctors = doctors.filter(name__icontains=search_query)

    # 3. Data ko template par bhejna
    context = {
        "doctors": doctors,
        "search_query": search_query,
    }
    return render(request, "admin/view_doctor.html", context)

@staff_member_required
def add_doctor(request):
    specialists = Specialist.objects.all()

    if request.method == "POST":
        name = request.POST.get("name")
        slug = request.POST.get("slug")
        photo = request.FILES.get("photo")
        qualification = request.POST.get("qualification")
        specialist_id = request.POST.get("specialist")
        experience = request.POST.get("experience")
        username = request.POST.get("username")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("add_doctor")

        specialist = get_object_or_404(Specialist, id=specialist_id)

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=name
        )
        user.is_staff = True
        user.save()

        Doctor.objects.create(
            name=name,
            user=user,
            slug=slug,
            image=photo,
            qualification=qualification,
            specialist=specialist,
            experience=experience
        )

        messages.success(request, "Doctor added successfully!")
        return redirect("view_doctor")

    return render(request, "admin/add_doctor.html", {"specialists": specialists})

def delete_doctor(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    doctor.delete()
    messages.success(request, "Doctor deleted successfully!")
    return redirect('view_doctor')

from django.shortcuts import render, get_object_or_404, redirect
from .models import Doctor # Apne model ka sahi naam check karein

def edit_doctor(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    
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
@staff_member_required
def view_patient(request):
    today = timezone.localtime(timezone.now()).date()

    today_patients = Appointment.objects.filter(date=today).order_by('time')
    all_patients = Appointment.objects.all().order_by('-date')

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
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import Appointment

@staff_member_required
def view_appointment(request):
    # Base query
    appointments = Appointment.objects.all().order_by('-date', 'time')

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
        "date_filter": date_filter
    })

# ================= SPECIALIST =================
@staff_member_required
def add_specialist(request):
    if request.method == "POST":
        name = request.POST.get("name")
        icon = request.FILES.get("icon")

        Specialist.objects.create(
            name=name,
            icon=icon
        )

        messages.success(request, "Specialist Added Successfully")
        return redirect("view_specialist")

    return render(request, "admin/add_specialist.html")


@staff_member_required
def view_specialist(request):
    specialists = Specialist.objects.all()
    return render(request, "admin/view_specialist.html", {
        "specialists": specialists
    })

@staff_member_required
def delete_specialist(request, pk):
    specialist = get_object_or_404(Specialist, pk=pk)
    specialist.delete()
    messages.success(request, "Specialist deleted successfully!")
    return redirect('view_specialist')


# ================= AMBULANCE =================
@staff_member_required
def ambulance_list(request):
    ambulances = Ambulance.objects.all()
    return render(request, "admin/ambulance_list.html", {
        "ambulances": ambulances
    })


@staff_member_required
def add_ambulance(request):
    if request.method == "POST":
        Ambulance.objects.create(
            name=request.POST.get("vehicle_number"),
            ambulance_type=request.POST.get("ambulance_type"),
            driver_name=request.POST.get("driver_name"),
            driver_phone=request.POST.get("driver_phone"),
            status=request.POST.get("status"),
        )
        return redirect("ambulance_list")

    return render(request, "admin/add_ambulance.html")


@staff_member_required
def all_ambulance_booked(request):
    bookings = AmbulanceBooking.objects.all()
    return render(request, "admin/all_ambulance_booked.html", {
        "bookings": bookings
    })


# ================= LAB =================
@staff_member_required
def add_lab_test(request):
    if request.method == "POST":
        LabTest.objects.create(
            test_name=request.POST.get("name"),
            price=request.POST.get("price"),
            description=request.POST.get("description")
        )
        return redirect("lab_test_list")

    return render(request, "admin/add_lab_test.html")


@staff_member_required
def lab_test_list(request):
    lab_tests = LabTest.objects.all()
    return render(request, "admin/lab_test_list.html", {
        "tests": lab_tests
    })


@staff_member_required
def all_lab_booked(request):
    bookings = LabBooking.objects.all()
    return render(request, "admin/all_lab_booked.html", {
        "bookings": bookings
    })


# ================= MEDICINE =================
@staff_member_required
def medicine_list(request):
    medicines = Medicine.objects.all()
    return render(request, "admin/medicine_list.html", {
        "medicines": medicines
    })


@staff_member_required
def add_medicine(request):
    if request.method == "POST":
        Medicine.objects.create(
            name=request.POST.get("name"),
            price=request.POST.get("price"),
            stock=request.POST.get("stock"),
            expiry_date=request.POST.get("expiry_date")
        )
        return redirect("medicine_list")

    return render(request, "admin/add_medicine.html")


@staff_member_required
def all_medicine_ordered(request):
    orders = MedicineOrder.objects.all()
    return render(request, "admin/all_medicine_ordered.html", {
        "orders": orders
    })
