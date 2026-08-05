from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.db.models import Q
from datetime import datetime, time
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from doctors.models import Doctor
from accounts.models import Patient
from appointments.models import Appointment
from payments.models import Payment
from notifications.notifications import (
    notify_appointment_booked,
    notify_appointment_cancelled,
)
from core.activity import log_activity
from core.views import get_current_hospital
from accounts.views import (
    is_valid_email_address,
    is_valid_indian_phone,
    is_patient_profile_complete,
)


@login_required(login_url='login')
def book_appointment(request, slug):
    doctor = get_object_or_404(Doctor, slug=slug)
    if doctor.hospital:
        request.session["hospital_id"] = doctor.hospital.id
        current_hospital = doctor.hospital
    else:
        current_hospital = get_current_hospital(request)

    if request.method == "POST":
        try:
            full_name = request.POST.get("name")
            email = (request.POST.get("email") or "").strip()
            phone = (request.POST.get("phone") or "").strip()
            date_str = request.POST.get("date")
            time_str = request.POST.get("time")
            message = request.POST.get("message")

            if not all([full_name, email, phone, date_str, time_str]):
                return JsonResponse({'success': False, 'message': 'All fields are required.'})

            if not is_valid_email_address(email):
                return JsonResponse({'success': False, 'message': 'Please enter a valid email address.'})

            if not is_valid_indian_phone(phone):
                return JsonResponse({'success': False, 'message': 'Phone number must be exactly 10 digits.'})

            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            selected_time = datetime.strptime(time_str, "%H:%M").time()

            now_local = timezone.localtime(timezone.now())
            current_date = now_local.date()
            current_time = now_local.time()

            start_limit = time(9, 0)
            end_limit = time(17, 0)

            if not (start_limit <= selected_time < end_limit):
                return JsonResponse({'success': False, 'message': 'Clinic is open from 9 AM to 5 PM.'})

            if selected_date < current_date:
                return JsonResponse({'success': False, 'message': 'Past date is not allowed.'})

            if selected_date == current_date and selected_time <= current_time:
                return JsonResponse({'success': False, 'message': 'Past time is not allowed.'})

            if selected_time.minute not in [0, 30]:
                return JsonResponse({'success': False, 'message': 'Only 30-minute slots are allowed.'})

            if Appointment.objects.filter(
                doctor=doctor,
                date=selected_date,
                time=selected_time
            ).exclude(status="Cancelled").exists():
                return JsonResponse({'success': False, 'message': 'This slot is already booked.'})

            fees = doctor.fees if doctor.fees else 500
            amount_in_paise = fees * 100

            appointment = Appointment.objects.create(
                user=request.user,
                hospital=current_hospital or doctor.hospital,
                doctor=doctor,
                name=full_name,
                email=email,
                phone=phone,
                date=selected_date,
                time=selected_time,
                message=message,
                status="Pending"
            )

            notify_appointment_booked(appointment)

            import razorpay
            from django.utils.crypto import get_random_string

            razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', '')
            is_test_mode = bool(razorpay_key and razorpay_key.startswith('rzp_test_'))
            order_id = ""
            amount_in_paise = fees * 100

            if is_test_mode:
                try:
                    client = razorpay.Client(
                        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                    )
                    order = getattr(client, 'order').create({
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "payment_capture": 1
                    })
                    order_id = order["id"]
                    amount_in_paise = order["amount"]
                except Exception as e:
                    is_test_mode = False

            if is_test_mode:
                return JsonResponse({
                    'success': True,
                    'pay_required': True,
                    'razorpay_options': {
                        'key': razorpay_key,
                        'amount': amount_in_paise,
                        'currency': 'INR',
                        'order_id': order_id,
                        'name': 'MediCare',
                        'description': 'Doctor Appointment Fee',
                        'prefill': {
                            'name': full_name,
                            'email': email,
                            'contact': phone
                        },
                        'theme': {
                            'color': '#2563eb'
                        }
                    },
                    'success_url': reverse('successful_payment'),
                    'failed_url': reverse('failed_payment'),
                    'doctor_id': doctor.id,
                    'appointment_id': appointment.id,
                    'order_id': order_id
                })
            else:
                success_url = reverse('my_appointments')
                return JsonResponse({
                    'success': True,
                    'pay_required': False,
                    'appointment_id': appointment.id,
                    'redirect_url': success_url,
                    'message': 'Appointment booked successfully!'
                })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Server Error: {str(e)}'})

    patient = Patient.objects.filter(user=request.user).first()
    return render(request, "appointments/book_appointment.html", {
        "doctor": doctor,
        "patient": patient,
    })


@login_required(login_url='login')
def edit_appointment(request, id):
    appointment = get_object_or_404(Appointment, id=id, user=request.user)

    if request.method == "POST":
        try:
            date_str = request.POST.get("date")
            time_str = request.POST.get("time")

            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            selected_time = datetime.strptime(time_str, "%H:%M").time()

            now_local = timezone.localtime(timezone.now())
            current_date = now_local.date()
            current_time = now_local.time()

            start_limit = time(9, 0)
            end_limit = time(17, 0)

            if not (start_limit <= selected_time < end_limit):
                messages.error(request, "Clinic is open from 9 AM to 5 PM.")
                return redirect('my_appointments')

            if selected_time.minute not in [0, 30]:
                messages.error(request, "Only 30-minute slots are allowed.")
                return redirect('my_appointments')

            if selected_date < current_date or (selected_date == current_date and selected_time <= current_time):
                messages.error(request, "Past date/time is not allowed.")
                return redirect('my_appointments')

            if Appointment.objects.filter(
                doctor=appointment.doctor,
                date=selected_date,
                time=selected_time
            ).exclude(id=appointment.id).exclude(status="Cancelled").exists():
                messages.error(request, "This slot is already booked.")
                return redirect('my_appointments')

            appointment.date = selected_date
            appointment.time = selected_time
            appointment.status = "Pending"
            appointment.save()

            messages.success(request, "Appointment updated successfully. Payment needs to be made again.")
            return redirect('my_appointments')

        except Exception as e:
            messages.error(request, f"Server Error: {str(e)}")
            return redirect('my_appointments')

    return render(request, "appointments/edit_appointment.html", {"appointment": appointment})


@login_required(login_url='login')
def get_booked_slots(request):
    doctor_id = request.GET.get("doctor_id")
    date_str = request.GET.get("date")
    current_appointment_id = request.GET.get("appointment_id")

    if not doctor_id or not date_str:
        return JsonResponse({"success": False, "booked_slots": []})

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "booked_slots": []})

    booked_qs = Appointment.objects.filter(
        doctor_id=doctor_id,
        date=selected_date
    ).exclude(status="Cancelled")

    if current_appointment_id:
        booked_qs = booked_qs.exclude(id=current_appointment_id)

    booked_slots = [a.time.strftime("%H:%M") for a in booked_qs]
    return JsonResponse({"success": True, "booked_slots": booked_slots})


@login_required(login_url='login')
@require_POST
def cancel_appointment(request, id):
    appointment = get_object_or_404(Appointment, id=id, user=request.user)

    if appointment.status in ("Cancelled", "Completed"):
        messages.warning(request, "This appointment cannot be cancelled.")
        return redirect('my_appointments')

    appointment.status = "Cancelled"
    appointment.save(update_fields=['status'])
    notify_appointment_cancelled(appointment, cancelled_by="patient")
    log_activity(
        actor=request.user,
        action="appointment_cancelled",
        target_type="appointment",
        target_id=str(appointment.id),
        description="Patient cancelled appointment",
        extra_data={"doctor_id": appointment.doctor.id},
    )
    messages.success(request, "Appointment cancelled successfully")
    return redirect('my_appointments')


@login_required(login_url='login')
def my_appointments(request):
    current_hospital = get_current_hospital(request)
    appointments = Appointment.objects.filter(
        user=request.user
    ).order_by('-date', '-time')
    if current_hospital:
        appointments = appointments.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True)).order_by('-date', '-time')
    return render(request, "appointments/my_appointments.html", {
        "appointments": appointments
    })


@login_required(login_url='login')
def patient_dashboard(request):
    current_hospital = get_current_hospital(request)
    patient, _ = Patient.objects.get_or_create(
        user=request.user,
        defaults={
            "name": request.user.first_name or request.user.username,
            "email": request.user.email,
            "hospital": current_hospital,
        }
    )
    if current_hospital and not patient.hospital:
        patient.hospital = current_hospital
        patient.save(update_fields=["hospital"])

    appointments = Appointment.objects.filter(user=request.user).select_related("doctor", "hospital").order_by('-date', '-time')
    if current_hospital:
        appointments = appointments.filter(Q(hospital=current_hospital) | Q(hospital__isnull=True)).order_by('-date', '-time')

    return render(request, "appointments/patient_dashboard.html", {
        "patient": patient,
        "appointments": appointments,
        "profile_complete": is_patient_profile_complete(patient),
    })


@login_required(login_url='login')
def download_appointment_slip(request, id):
    appointment = get_object_or_404(Appointment.objects.select_related("doctor", "hospital"), id=id, user=request.user)
    payment = Payment.objects.filter(appointment=appointment, status=True).order_by("-created_at").first()
    amount = payment.amount if payment else (appointment.doctor.fees or 500)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFillColor(colors.HexColor("#f3f7fc"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    card_x = 28
    card_y = 34
    card_w = width - 56
    card_h = height - 68

    pdf.setFillColor(colors.white)
    pdf.roundRect(card_x, card_y, card_w, card_h, 14, fill=1, stroke=0)

    header_h = 92
    pdf.setFillColor(colors.HexColor("#165a9a"))
    pdf.roundRect(card_x, height - card_y - header_h, card_w, header_h, 14, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(card_x + 18, height - card_y - 35, "MEDICARE")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(card_x + 18, height - card_y - 52, "Compassionate Care, Trusted Excellence")

    generated_text = timezone.localtime(timezone.now()).strftime("%d %b %Y, %I:%M %p")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(card_x + card_w - 16, height - card_y - 30, "SLIP GENERATED")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(card_x + card_w - 16, height - card_y - 48, generated_text)

    y = height - card_y - header_h - 34
    pdf.setFillColor(colors.HexColor("#1c2f47"))
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(card_x + card_w / 2, y, "APPOINTMENT SLIP")

    y -= 42
    summary_h = 66
    summary_w = card_w - 28
    summary_x = card_x + 14
    pdf.setFillColor(colors.HexColor("#eef3f9"))
    pdf.roundRect(summary_x, y - summary_h, summary_w, summary_h, 8, fill=1, stroke=0)

    for i in range(1, 4):
        x = summary_x + (summary_w / 4) * i
        pdf.setStrokeColor(colors.HexColor("#d5dfec"))
        pdf.line(x, y - summary_h + 8, x, y - 8)

    status = (appointment.status or "Pending").strip()
    status_color = {
        "Pending": colors.HexColor("#f59e0b"),
        "Confirmed": colors.HexColor("#0ea5a8"),
        "Completed": colors.HexColor("#188a52"),
        "Cancelled": colors.HexColor("#dc2626"),
    }.get(status, colors.HexColor("#64748b"))

    blocks = [
        ("APPOINTMENT ID", str(appointment.id)),
        ("STATUS", status),
        ("DATE", appointment.date.strftime("%d %b %Y")),
        ("TIME", appointment.time.strftime("%I:%M %p")),
    ]

    for idx, (k, v) in enumerate(blocks):
        bx = summary_x + (summary_w / 4) * idx + (summary_w / 8)
        pdf.setFillColor(colors.HexColor("#35547a"))
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawCentredString(bx, y - 20, k)

        if k == "STATUS":
            pill_w = max(58, len(v) * 6.2 + 16)
            pill_x = bx - (pill_w / 2)
            pill_y = y - 46
            pdf.setFillColor(status_color)
            pdf.roundRect(pill_x, pill_y, pill_w, 18, 9, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawCentredString(bx, pill_y + 5, v)
        else:
            pdf.setFillColor(colors.HexColor("#1c2f47"))
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawCentredString(bx, y - 43, v)

    y -= (summary_h + 20)
    card_h2 = 132
    gap = 12
    col_w = (summary_w - gap) / 2

    def draw_detail_card(x, top_y, title, rows):
        pdf.setFillColor(colors.white)
        pdf.roundRect(x, top_y - card_h2, col_w, card_h2, 8, fill=1, stroke=0)
        pdf.setStrokeColor(colors.HexColor("#d8e2ef"))
        pdf.roundRect(x, top_y - card_h2, col_w, card_h2, 8, fill=0, stroke=1)
        pdf.setFillColor(colors.HexColor("#165a9a"))
        pdf.roundRect(x, top_y - 28, col_w, 28, 8, fill=1, stroke=0)
        pdf.rect(x, top_y - 28, col_w, 14, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(x + 10, top_y - 18, title)

        ry = top_y - 45
        for label, value in rows:
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(colors.HexColor("#6b7c93"))
            pdf.drawString(x + 10, ry, label)
            pdf.setFillColor(colors.HexColor("#1f3551"))
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawRightString(x + col_w - 10, ry, value[:38])
            ry -= 24

    draw_detail_card(
        summary_x,
        y,
        "PATIENT DETAILS",
        [
            ("Name", appointment.name or "N/A"),
            ("Phone", appointment.phone or "N/A"),
            ("Email", appointment.email or "N/A"),
        ],
    )

    draw_detail_card(
        summary_x + col_w + gap,
        y,
        "DOCTOR & HOSPITAL DETAILS",
        [
            ("Doctor", f"Dr. {appointment.doctor.name}" if appointment.doctor else "N/A"),
            ("Specialist", appointment.doctor.specialist.name if appointment.doctor and appointment.doctor.specialist else "N/A"),
            ("Hospital", appointment.hospital.name if appointment.hospital else "N/A"),
        ],
    )

    y -= (card_h2 + 16)
    pay_h = 95
    pdf.setFillColor(colors.HexColor("#eaf7ef"))
    pdf.roundRect(summary_x, y - pay_h, summary_w, pay_h, 8, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#c9e8d3"))
    pdf.roundRect(summary_x, y - pay_h, summary_w, pay_h, 8, fill=0, stroke=1)

    pdf.setFillColor(colors.HexColor("#1d7a48"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(summary_x + 10, y - 18, "PAYMENT DETAILS")

    inner_x = summary_x + 10
    inner_y = y - 80
    inner_w = summary_w - 20
    inner_h = 48
    pdf.setFillColor(colors.white)
    pdf.roundRect(inner_x, inner_y, inner_w, inner_h, 6, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#d7ecdf"))
    pdf.roundRect(inner_x, inner_y, inner_w, inner_h, 6, fill=0, stroke=1)

    for i in range(1, 3):
        x = inner_x + (inner_w / 3) * i
        pdf.setStrokeColor(colors.HexColor("#e4efe8"))
        pdf.line(x, inner_y + 8, x, inner_y + inner_h - 8)

    pay_cells = [
        ("Payment ID", payment.payment_id if payment else "N/A"),
        ("Order ID", payment.order_id if payment else "N/A"),
        ("Amount", f"INR {amount}"),
    ]
    for idx, (k, v) in enumerate(pay_cells):
        cx = inner_x + (inner_w / 3) * idx + 8
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(colors.HexColor("#6a7e74"))
        pdf.drawString(cx, inner_y + inner_h - 14, k.upper())
        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(colors.HexColor("#1f3a2d"))
        pdf.drawString(cx, inner_y + 13, v[:30])

    footer_y = card_y + 16
    pdf.setFillColor(colors.HexColor("#165a9a"))
    pdf.roundRect(summary_x, footer_y, summary_w, 24, 6, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(summary_x + summary_w / 2, footer_y + 8, "Please carry this slip to the hospital. For any queries, contact support.")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="appointment-slip-{appointment.id}.pdf"'
    return response
