from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone

from datetime import datetime, timedelta, time

import razorpay

from .models import *


# ================= RAZORPAY CLIENT =================
client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


# ================= HOME =================
def home(request):
    specialists = Specialist.objects.all()
    ambulances = Ambulance.objects.all()

    return render(request, "home.html", {
        "specialists": specialists,
        "ambulances": ambulances
    })


# ================= DOCTOR =================
@login_required(login_url='login')
def doctor_dashboard(request):
    doctor = Doctor.objects.filter(user=request.user).first()
    return render(request, 'doctor/doctor_dashboard.html', {"doctor": doctor})


def doctor_profile(request, slug):
    doctor = get_object_or_404(Doctor, slug=slug)
    return render(request, "doctor/doctor_profile.html", {"doctor": doctor})


def specialist_doctors(request, id):
    specialist = get_object_or_404(Specialist, id=id)
    doctors = Doctor.objects.filter(specialist=specialist)

    return render(request, "doctors.html", {
        "specialist": specialist,
        "doctors": doctors
    })


# ================= BOOK APPOINTMENT =================
@login_required(login_url='login')
def book_appointment(request, slug):
    doctor = get_object_or_404(Doctor, slug=slug)

    if request.method == "POST":
        try:
            full_name = request.POST.get("name")
            email = request.POST.get("email")
            phone = request.POST.get("phone")
            date_str = request.POST.get("date")
            time_str = request.POST.get("time")
            message = request.POST.get("message")

            if not all([full_name, email, phone, date_str, time_str]):
                return JsonResponse({'success': False, 'message': 'Saari fields bharna zaroori hai.'})

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
            ).exists():
                return JsonResponse({'success': False, 'message': 'Ye slot already booked hai.'})

            fees = doctor.fees if doctor.fees else 500
            amount_in_paise = int(fees) * 100

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

    appointment.status = "Confirmed"
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
    return render(request, "patient/patient_dashboard.html")


@login_required(login_url='login')
def patient_profile(request):
    return render(request, "patient/patient_profile.html", {"user": request.user})


@login_required(login_url='login')
def my_appointments(request):
    appointments = Appointment.objects.filter(
        user=request.user
    ).order_by('-date', '-time')
    return render(request, "patient/my_appointments.html", {
        "appointments": appointments
    })


# ================= AUTH =================
def register_view(request):
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if not all([full_name, username, email, password1, password2]):
            messages.error(request, "All fields required")
            return redirect('register')

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=full_name
        )

        Patient.objects.create(user=user, name=full_name, email=email)

        messages.success(request, "Account created successfully")
        return redirect('login')

    return render(request, 'register.html')


def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            if user.is_superuser:
                return redirect('/admin/')
            elif user.is_staff:
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


# ================= LAB =================
@login_required(login_url='login')
def lab_booking(request):
    tests = LabTest.objects.all()

    if request.method == "POST":
        test_id = request.POST.get("test")
        date = request.POST.get("date")
        time_ = request.POST.get("time")
        address = request.POST.get("address")

        if not all([test_id, date, time_, address]):
            messages.error(request, "All fields required")
            return redirect("lab_booking")

        test = get_object_or_404(LabTest, id=test_id)

        LabBooking.objects.create(
            patient=request.user,
            test=test,
            date=date,
            time=time_,
            address=address
        )

        messages.success(request, "Lab test booked successfully")
        return redirect("home")

    return render(request, "lab_booking.html", {"tests": tests})


# ================= AMBULANCE =================
@login_required(login_url='login')
def ambulance_booking(request):
    ambulances = Ambulance.objects.filter(status="Available")

    if request.method == "POST":
        ambulance_id = request.POST.get("ambulance")
        pickup = request.POST.get("pickup")
        drop = request.POST.get("drop")
        date = request.POST.get("date")
        time_ = request.POST.get("time")

        ambulance = get_object_or_404(Ambulance, id=ambulance_id)

        AmbulanceBooking.objects.create(
            patient=request.user,
            ambulance=ambulance,
            pickup_location=pickup,
            drop_location=drop,
            date=date,
            time=time_
        )

        ambulance.status = "Busy"
        ambulance.save()

        messages.success(request, "Ambulance booked successfully")
        return redirect("home")

    return render(request, "book_ambulance.html", {"ambulances": ambulances})


# ================= MEDICINE =================
@login_required(login_url='login')
def medicine_order(request):
    medicines = Medicine.objects.filter(stock__gt=0)

    if request.method == "POST":
        medicine_id = request.POST.get("medicine")
        quantity = int(request.POST.get("quantity", 1))
        address = request.POST.get("address")

        medicine = get_object_or_404(Medicine, id=medicine_id)

        MedicineOrder.objects.create(
            patient=request.user,
            medicine=medicine,
            quantity=quantity,
            address=address
        )

        messages.success(request, "Medicine ordered successfully")
        return redirect("home")

    return render(request, "medicine_order.html", {"medicines": medicines})   