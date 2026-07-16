from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from doctors.models import Doctor
from appointments.models import Appointment
from accounts.models import Patient
from payments.models import Payment
from accounts.views import is_patient_profile_complete


from django.utils.crypto import get_random_string

from django.conf import settings
import razorpay

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
    
    razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
    is_test_mode = razorpay_key.startswith('rzp_test_')
    
    if is_test_mode:
        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            order = client.order.create({  # type: ignore
                "amount": fees * 100,
                "currency": "INR",
                "payment_capture": 1
            })
            order_id = order["id"]
            amount_in_paise = order["amount"]
        except Exception as e:
            # Fallback to mock if API fails
            order_id = "mock_ord_" + get_random_string(10).lower()
            amount_in_paise = fees * 100
            is_test_mode = False
    else:
        order_id = "mock_ord_" + get_random_string(10).lower()
        amount_in_paise = fees * 100

    return render(request, "payments/payment.html", {
        "doctor": doctor,
        "order_id": order_id,
        "amount": fees,
        "amount_in_paise": amount_in_paise,
        "razorpay_key": razorpay_key,
        "is_test_mode": is_test_mode,
        "appointment_id": appointment.id if appointment else None
    })


from django.urls import reverse

@login_required(login_url='login')
def successfull_payment(request):
    payment_id = request.GET.get("payment_id")
    order_id = request.GET.get("order_id")
    doctor_id = request.GET.get("doctor_id")
    appointment_id = request.GET.get("appointment_id")
    signature = request.GET.get("signature")

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

    # signature verification
    razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
    is_real_razorpay = order_id and not order_id.startswith('mock_ord_')

    # If it is a real Razorpay order, verify signature
    if is_real_razorpay:
        if not signature:
            messages.error(request, "Payment verification signature missing.")
            return redirect(reverse('failed_payment') + f"?error_message=Verification signature missing&doctor_id={doctor_id}&appointment_id={appointment.id}&order_id={order_id}&payment_id={payment_id}")
        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            # Verify signature
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
        except Exception as e:
            messages.error(request, f"Signature verification failed: {str(e)}")
            return redirect(reverse('failed_payment') + f"?error_message=Signature verification failed: {str(e)}&doctor_id={doctor_id}&appointment_id={appointment.id}&order_id={order_id}&payment_id={payment_id}")

    # Mark the appointment as Pending and confirm payment in the DB (is_paid counterpart)
    # Mark the payment status as True (Paid)
    payment = None
    if payment_id:
        # Prevent duplicate payments by checking if it exists
        existing_payment = Payment.objects.filter(payment_id=payment_id).first()
        if existing_payment:
            payment = existing_payment
            if not payment.status:
                payment.status = True
                payment.save()
        else:
            payment = Payment.objects.create(
                user=request.user,
                appointment=appointment,
                payment_id=payment_id,
                order_id=order_id,
                amount=doctor.fees if doctor.fees else 500,
                status=True
            )

    appointment.status = "Pending"
    appointment.save()

    patient = Patient.objects.filter(user=request.user).first()
    messages.success(request, "Appointment booked successfully.")
    if not is_patient_profile_complete(patient):
        messages.warning(request, "Please complete your profile details for faster future bookings.")

    return render(request, "payments/success.html", {
        "appointment": appointment,
        "payment": payment,
        "doctor": doctor,
        "amount": doctor.fees if doctor.fees else 500,
    })


@login_required(login_url='login')
def failed_payment(request):
    error_message = request.GET.get("error_message", "Transaction verification failed or cancelled by user.")
    doctor_id = request.GET.get("doctor_id")
    appointment_id = request.GET.get("appointment_id")
    
    doctor = None
    if doctor_id:
        doctor = get_object_or_404(Doctor, id=doctor_id)
        
    appointment = None
    if appointment_id and appointment_id != 'None':
        appointment = Appointment.objects.filter(
            id=appointment_id,
            user=request.user
        ).first()
        
    if not appointment and doctor:
        appointment = Appointment.objects.filter(
            doctor=doctor,
            user=request.user
        ).order_by('-created_at').first()
        
    if not appointment:
        messages.error(request, "Appointment context not found")
        return redirect("patient_dashboard")
        
    # Mark payment as failed if object exists
    order_id = request.GET.get("order_id")
    payment_id = request.GET.get("payment_id")
    
    if payment_id:
        Payment.objects.filter(payment_id=payment_id).update(status=False)
        
    return render(request, "payments/failure.html", {
        "appointment": appointment,
        "doctor": doctor or appointment.doctor,
        "error_message": error_message,
        "amount": doctor.fees if (doctor and doctor.fees) else 500,
    })
