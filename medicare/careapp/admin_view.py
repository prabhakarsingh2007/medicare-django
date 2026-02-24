from django.shortcuts import render,redirect
from .models import *
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required


from django.utils import timezone

@staff_member_required
def dashboard(request):
    today = timezone.now().date()
    
    context = {
        "doctor_count": Doctor.objects.count(),
        "patient_count": Patient.objects.count(),
        "appointment_count": Appointment.objects.count(),
        # Naye fields dashboard ko live banane ke liye
        "today_count": Appointment.objects.filter(date=today).count(),
        "recent_appointments": Appointment.objects.all().order_by('-id')[:5], 
        "today_date": today,
    }
    return render(request, "admin/dashboard.html", context)

@staff_member_required
def view_doctor(request):
     doctors = Doctor.objects.all().order_by('specialist__name', 'name')
     return render(request, "admin/view_doctor.html",{"doctors": doctors})
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from .models import Appointment, Patient

@staff_member_required
def view_patient(request):
    # Timezone fix for India (Asia/Kolkata)
    today = timezone.localtime(timezone.now()).date()
    
    # Aaj ke patients
    today_patients = Appointment.objects.filter(date=today).order_by('time')
    
    # Saare patients (History)
    all_patients = Appointment.objects.all().order_by('-date')

    context = {
        "today_patients": today_patients,
        "all_patients": all_patients,
        "today_date": today,
    }

    # AGAR ERROR AA RAHA HAI: To check karein file ka naam 'view_patient.html' hai ya 'manage_patients.html'
    # Main yahan 'view_patient.html' use kar raha hoon kyunki aksar yahi default hota hai
    try:
        return render(request, "admin/view_patient.html", context)
    except:
        return render(request, "admin/manage_patients.html", context)


@staff_member_required
def view_appointment(request):
    appointments = Appointment.objects.all().order_by('-date','time')
    return render(request, 'admin/view_appoiment.html', {"appointments": appointments})

@staff_member_required
def add_doctor(request):
    specialists = Specialist.objects.all()

    if request.method == "POST":
        # Form se data lena
        name = request.POST.get("name")
        slug = request.POST.get("slug")
        photo = request.FILES.get("photo")
        qualification = request.POST.get("qualification")
        specialist_id = request.POST.get("specialist")
        experience = request.POST.get("experience")
        phone = request.POST.get("phone")
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists. Choose a different username.")
            return redirect("add_doctor")

        # Specialist fetch karna
        specialist = Specialist.objects.get(id=specialist_id)

        # Doctor user create karna (login ke liye)
        user = User.objects.create_user(username=username, password=password, first_name=name)
        user.is_staff = True
      
        user.save()

        # Doctor object create karna
        doctor = Doctor.objects.create(
            # Agar Doctor model me OneToOneField User ke sath hai
            name=name,
            user=user,
            slug=slug,
            image=photo,
            qualification=qualification,
            specialist=specialist,
            experience=experience
        )

        messages.success(request, "Doctor added successfully!")
        return redirect("view_doctor")  # Doctor list page pe redirect

    return render(request, "admin/add_doctor.html", {"specialists": specialists})





    



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
    return render(request, "admin/view_specialist.html", {"specialists": specialists})



@staff_member_required
def ambulance_list(request):
    ambulances = Ambulance.objects.all()
    return render(request, "admin/ambulance_list.html", {"ambulances": ambulances})



@staff_member_required
def add_lab_test(request):
    if request.method == "POST":
        test_name = request.POST.get("name")
        price = request.POST.get("price")
        description = request.POST.get("description")

        LabTest.objects.create(
            test_name=test_name,
            price=price,
            description=description
        )
        return redirect("lab_test_list")            
    return render(request, "admin/add_lab_test.html")


@staff_member_required
def lab_test_list(request):
    lab_tests = LabTest.objects.all()
    return render(request, "admin/lab_test_list.html", {"tests": lab_tests})


@staff_member_required
def medicine_list(request):
    medicines = Medicine.objects.all()
    return render(request, "admin/medicine_list.html", {"medicines": medicines})


@staff_member_required
def add_ambulance(request):
    if request.method == "POST":
        # Model fields: name, ambulance_type, driver_name, driver_phone, status
        Ambulance.objects.create(
            name=request.POST.get("vehicle_number"), # Map vehicle number to 'name'
            ambulance_type=request.POST.get("ambulance_type"),
            driver_name=request.POST.get("driver_name"),
            driver_phone=request.POST.get("driver_phone"),
            status=request.POST.get("status"),
        )
        return redirect("ambulance_list")

    return render(request, "admin/add_ambulance.html")


@staff_member_required
def add_medicine(request):
    if request.method == "POST":
        # Form se data nikalna
        name = request.POST.get("name")
        price = request.POST.get("price")
        stock = request.POST.get("stock")
        expiry_date = request.POST.get("expiry_date")
        
        # Database mein save karna
        Medicine.objects.create(
            name=name,
            price=price,
            stock=stock,
            expiry_date=expiry_date
        )
        return redirect("medicine_list")

    return render(request, "admin/add_medicine.html")






@staff_member_required
def all_ambulance_booked(request):
    bookings = AmbulanceBooking.objects.all()
    return render(request, "admin/all_ambulance_booked.html", {"bookings": bookings})



@staff_member_required
def all_lab_booked(request):
    bookings = LabBooking.objects.all()
    return render(request, "admin/all_lab_booked.html", {"bookings": bookings}) 



@staff_member_required
def all_medicine_ordered(request):  
    orders = MedicineOrder.objects.all()
    return render(request, "admin/all_medicine_ordered.html", {"orders": orders})   

