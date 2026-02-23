from django.shortcuts import render,redirect, get_object_or_404
from .models import *
import razorpay
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from datetime import date as today_date, datetime
from django.utils import timezone

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def home(request):
    specialists = Specialist.objects.all()
    ambulances = Ambulance.objects.all()

    return render(request, "home.html", {
        "specialists": specialists,
        "ambulances": ambulances
    })


@login_required(login_url='login')
def doctor_dashboard(request):
    doctor = Doctor.objects.filter(user=request.user).first()
    return render(request, 'doctor/doctor_dashboard.html',{"doctor": doctor})



def specialist_doctors(request, id):
    specialist = Specialist.objects.get(id=id)
    doctors = Doctor.objects.filter(specialist=specialist)

    return render(
        request,
        "doctors.html",
        {
            "specialist": specialist,
            "doctors": doctors
        }
    )

from datetime import datetime
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils import timezone
from datetime import datetime, time

@login_required(login_url='login')
def book_appointment(request, slug):
    doctor = get_object_or_404(Doctor, slug=slug)

    if request.method == "POST":
        try:
            # 1. Data Lena
            full_name = request.POST.get("name")
            email = request.POST.get("email")
            phone = request.POST.get("phone")
            date_str = request.POST.get("date")
            time_str = request.POST.get("time")
            message = request.POST.get("message")

            # 2. Basic Validation
            if not all([full_name, email, phone, date_str, time_str]):
                return JsonResponse({'success': False, 'message': 'Saari fields bharna zaroori hai.'})

            # Time aur Date Parse karein
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            selected_time = datetime.strptime(time_str, "%H:%M").time()
            
            # --- VALIDATION START ---
            
            # A. Current Date aur Time (Local)
            now_local = timezone.localtime(timezone.now())
            current_date = now_local.date()
            current_time = now_local.time()

            # B. Working Hours Check (9 AM to 5 PM)
            start_limit = time(9, 0)
            end_limit = time(17, 0) # 5 PM tak bookings, yani aakhri slot 4:30-5:00
            if not (start_limit <= selected_time < end_limit):
                return JsonResponse({'success': False, 'message': 'Clinic sirf subah 9 AM se sham 5 PM tak khula hai.'})

            # C. Backdate Check
            if selected_date < current_date:
                return JsonResponse({'success': False, 'message': 'Aap purani date book nahi kar sakte.'})

            # D. Past Time Check (Agar aaj ki date hai)
            if selected_date == current_date:
                if selected_time <= current_time:
                    return JsonResponse({'success': False, 'message': 'Ye waqt beet chuka hai. Future ka slot choose karein.'})

            # E. 30-Minute Slot Validation
            if selected_time.minute not in [0, 30]:
                return JsonResponse({'success': False, 'message': 'Invalid time format. Sirf 30-minute slots hi available hain.'})

            # --- VALIDATION END ---

            # 4. Duplicate Slot Check
            if Appointment.objects.filter(doctor=doctor, date=selected_date, time=selected_time).exists():
                return JsonResponse({'success': False, 'message': 'Ye slot pehle se booked hai. Dusra slot chunein.'})

            # 5. Fees Logic
            raw_fees = doctor.fees if doctor.fees is not None else 500
            amount_in_paise = int(float(raw_fees) * 100)

            # 6. Create Pending Appointment
            appointment = Appointment.objects.create(
                user=request.user,
                doctor=doctor,
                name=full_name,
                email=email,
                phone=phone,
                date=selected_date,
                time=selected_time,
                message=message,
                status="Pending"
            )

            # 7. Razorpay Order
            order_data = {
                "amount": amount_in_paise,
                "currency": "INR",
                "payment_capture": 1
            }
            razorpay_order = client.order.create(data=order_data)

            return JsonResponse({
                'success': True,
                'order_id': razorpay_order['id'],
                'amount': razorpay_order['amount'],
                'razorpay_key': settings.RAZORPAY_KEY_ID,
                'appointment_id': appointment.id
            })

        except Exception as e:
            print(f"ERROR: {str(e)}") 
            return JsonResponse({'success': False, 'message': f'Server Error: {str(e)}'})

    return render(request, "book_appointment.html", {"doctor": doctor})


@login_required(login_url='login')
def payment(request, id):
    doctor = Doctor.objects.get(id=id)
    appointment_id = request.GET.get("appointment_id") or request.POST.get("appointment_id")
    if not appointment_id:
        # fallback: try to get latest appointment for this doctor and user
        appointment = Appointment.objects.filter(doctor=doctor).order_by('-created_at').first()
        appointment_id = appointment.id if appointment else None
    else:
        appointment = Appointment.objects.get(id=appointment_id)

    # Do NOT update appointment status here; only after payment success

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    order = client.order.create({
        "amount": int(doctor.fees or 700) * 100,
        "currency": "INR",
        "payment_capture": 1
    })

    context = {
        "doctor": doctor,
        "order_id": order["id"],
        "amount": order["amount"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "appointment_id": appointment_id
    }

    return render(request, "payment.html", context)

@login_required(login_url='login')
def successfull_payment(request):
    # Data nikalna (Inke naam JavaScript se match hone chahiye)
    payment_id = request.GET.get("payment_id")
    order_id = request.GET.get("order_id")
    doctor_id = request.GET.get("doctor_id")
    appointment_id = request.GET.get("appointment_id")
    
    # 1. Doctor fetch karein
    doctor = get_object_or_404(Doctor, id=doctor_id)

    # 2. Appointment dhundna
    appointment = None
    if appointment_id and appointment_id != 'None':
        try:
            appointment = Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            appointment = None

    # Fallback agar appointment_id nahi mila
    if not appointment:
        appointment = Appointment.objects.filter(
            doctor=doctor, 
            user=request.user
        ).order_by('-created_at').first()

    if not appointment:
        return render(request, "appointment_success.html", {
            "doctor": doctor,
            "error": "Appointment details not found."
        })

    # 3. Status update aur Payment record banana
    appointment.status = "Confirmed"
    appointment.save()

    # Payment record (Maan lijiye aapka Payment model status=BooleanField hai)
    payment_amount = doctor.fees if doctor.fees else 500
    Payment.objects.get_or_create(
        payment_id=payment_id,
        defaults={
            'appointment': appointment,
            'order_id': order_id,
            'amount': payment_amount,
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

@login_required(login_url='login')
def patient_dashboard(request):
    return render(request, "patient/patient_dashboard.html")


@login_required(login_url='patient_login')
def patient_profile(request):
    user = request.user
    return render(request, "patient/patient_profile.html", {
        "user": user
    })
 
@login_required(login_url='login')
def my_appointments(request):
    appointment = Appointment.objects.filter()
    return render(request,"patient/my_appointments.html", {'appointments':appointment})


def register_view(request):
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Simple validation
        if not full_name or not email or not password1 or not password2:
            messages.error(request, "All fields are required!")
            return redirect('register')

        if password1 != password2:
            messages.error(request, "Passwords do not match!")
            return redirect('register')

        if User.objects.filter(username=email).exists():
            messages.error(request, "Email is already registered!")
            return redirect('register')

        # Create user
        user = User.objects.create_user(username=username, email=email, password=password1, first_name=full_name)
        user.save()

        Patient.objects.create(user=user, name=full_name, email=email)

        messages.success(request, "Account created successfully! Please login.")
        return redirect('login')

    return render(request, 'register.html')


def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # ===== ROLE BASED REDIRECT =====
            if user.is_superuser:
                messages.success(request, "Admin Login Successful")
                return redirect('/admin/')   # Django admin panel

            elif user.is_staff:
                messages.success(request, "Doctor Login Successful")
                return redirect('doctor_dashboard')

            else:
                messages.success(request, "Patient Login Successful")
                return redirect('home')

        else:
            messages.error(request, "Invalid Username or Password")
            return redirect('login')

    return render(request, "login.html")


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')




def about(request):
    return render(request, "extra/about.html")


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        message = request.POST.get("message")

        # Yaha tum database save ya email send kar sakte ho
        print(name, email, phone, message)

        messages.success(request, "Message Sent Successfully!")

    return render(request, "extra/contact.html")



@login_required(login_url='login')
def lab_booking(request):

    tests = LabTest.objects.all()

    if request.method == "POST":
        test_id = request.POST.get("test")
        date = request.POST.get("date")
        time = request.POST.get("time")
        address = request.POST.get("address")

        test = LabTest.objects.get(id=test_id)

        LabBooking.objects.create(
            patient=request.user,
            test=test,
            date=date,
            time=time,
            address=address
        )

        messages.success(request, "Lab test has been booked successfully!")

        return redirect("home")

    return render(request, "lab_booking.html", {"tests": tests})






@login_required(login_url='login')
def ambulance_booking(request):
    ambulances = Ambulance.objects.filter(status="Available")

    if request.method == "POST":
        ambulance_id = request.POST.get("ambulance")
        pickup = request.POST.get("pickup")
        drop = request.POST.get("drop")
        date = request.POST.get("date")
        time = request.POST.get("time")

        selected_ambulance = get_object_or_404(Ambulance, id=ambulance_id)

        AmbulanceBooking.objects.create(
            patient=request.user,
            ambulance=selected_ambulance,
            pickup_location=pickup,
            drop_location=drop,
            date=date,
            time=time
        )

        selected_ambulance.status = "Busy"
        selected_ambulance.save()

        # Success Message yahan add karein
        messages.success(request, f"Ambulance {selected_ambulance.name} has been booked successfully! Driver will contact you shortly.")

        return redirect("home") # Redirecting to home

    return render(request, "book_ambulance.html", {"ambulances": ambulances})


@login_required(login_url='login')
def medicine_order(request):

    medicines = Medicine.objects.filter(stock__gt=0)

    if request.method == "POST":
        medicine_id = request.POST.get("medicine")
        quantity = int(request.POST.get("quantity"))
        address = request.POST.get("address")

        medicine = Medicine.objects.get(id=medicine_id)

        MedicineOrder.objects.create(
            patient=request.user,
            medicine=medicine,
            quantity=quantity,
            address=address
        )
        
        messages.success(request, "Your medicine has been ordered successfully !")


        return redirect("home")

    return render(request, "medicine_order.html", {"medicines": medicines})



