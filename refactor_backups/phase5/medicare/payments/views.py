from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
import razorpay

from doctors.models import Doctor
from appointments.models import Appointment
from accounts.models import Patient
from payments.models import Payment
from accounts.views import is_patient_profile_complete

client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


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

    return render(request, "payments/payment.html", {
        "doctor": doctor,
        "order_id": order["id"],
        "amount": order["amount"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "appointment_id": appointment.id if appointment else None
    })


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
        messages.error(request, "Appointment not found")
        return redirect("patient_dashboard")

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

    patient = Patient.objects.filter(user=request.user).first()
    messages.success(request, "Appointment booked successfully.")
    if not is_patient_profile_complete(patient):
        messages.warning(request, "Please complete your profile details for faster future bookings.")
    return redirect("patient_dashboard")
