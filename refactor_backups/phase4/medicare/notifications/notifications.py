import logging
from django.conf import settings
from django.core.mail import send_mail
import requests

logger = logging.getLogger(__name__)


def send_email_notification(subject, message, recipient_list):
    recipients = [email for email in recipient_list if email]
    if not recipients:
        return False

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.warning("Email notification failed: %s", exc)
        return False


def send_sms_notification(phone, message):
    if not getattr(settings, "NOTIFICATIONS_ENABLE_SMS", False):
        return False

    gateway_url = getattr(settings, "SMS_GATEWAY_URL", "")
    api_key = getattr(settings, "SMS_GATEWAY_API_KEY", "")

    if not (gateway_url and api_key and phone):
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": phone,
        "message": message,
        "sender": getattr(settings, "SMS_GATEWAY_SENDER_ID", "MEDCARE"),
    }

    try:
        response = requests.post(gateway_url, json=payload, headers=headers, timeout=8)
        return response.status_code in (200, 201, 202)
    except Exception as exc:
        logger.warning("SMS notification failed: %s", exc)
        return False

def send_fast2sms_otp(phone, otp):
    api_key = getattr(settings, 'FAST2SMS_API_KEY', '')
    if not api_key:
        print(f"FAST2SMS_API_KEY not found. Fake sending OTP {otp} to {phone}")
        return False
        
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = f"variables_values={otp}&route=otp&numbers={phone}"
    headers = {
        'authorization': api_key,
        'Content-Type': "application/x-www-form-urlencoded",
        'Cache-Control': "no-cache",
    }
    try:
        response = requests.post(url, data=payload, headers=headers)
        return response.ok
    except Exception as e:
        logger.warning("Fast2SMS notification failed: %s", e)
        return False


def notify_appointment_booked(appointment):
    dt_text = f"{appointment.date} at {appointment.time}"
    subject = "Appointment Booked Successfully"
    body = (
        f"Hello {appointment.name},\n\n"
        f"Your appointment with Dr. {appointment.doctor.name} is booked for {dt_text}.\n"
        f"Current status: {appointment.status}.\n\n"
        "Thank you."
    )

    sms_text = (
        f"MediCare: Appointment booked with Dr. {appointment.doctor.name} on "
        f"{appointment.date} {appointment.time}. Status: {appointment.status}."
    )

    send_email_notification(subject, body, [appointment.email, appointment.user.email if appointment.user else None])
    send_sms_notification(appointment.phone, sms_text)


def notify_appointment_confirmed(appointment):
    dt_text = f"{appointment.date} at {appointment.time}"
    subject = "Appointment Confirmed"
    body = (
        f"Hello {appointment.name},\n\n"
        f"Your appointment with Dr. {appointment.doctor.name} for {dt_text} has been confirmed.\n\n"
        "Please arrive 10 minutes early."
    )

    sms_text = f"MediCare: Appointment confirmed with Dr. {appointment.doctor.name} on {appointment.date} {appointment.time}."
    send_email_notification(subject, body, [appointment.email, appointment.user.email if appointment.user else None])
    send_sms_notification(appointment.phone, sms_text)


def notify_appointment_cancelled(appointment, cancelled_by="system"):
    dt_text = f"{appointment.date} at {appointment.time}"
    subject = "Appointment Cancelled"
    body = (
        f"Hello {appointment.name},\n\n"
        f"Your appointment with Dr. {appointment.doctor.name} for {dt_text} has been cancelled by {cancelled_by}.\n\n"
        "Please rebook a new slot if required."
    )

    sms_text = f"MediCare: Your appointment on {appointment.date} {appointment.time} is cancelled."
    send_email_notification(subject, body, [appointment.email, appointment.user.email if appointment.user else None])
    send_sms_notification(appointment.phone, sms_text)
