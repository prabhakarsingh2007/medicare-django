# Proxy imports to maintain views and templates compilation during the refactoring transition.
from core.models import Specialist, Hospital, ActivityLog
from accounts.models import Patient, HospitalAdminProfile, EmailVerificationToken, default_email_token_expiry
from doctors.models import Doctor
from appointments.models import Appointment
from payments.models import Payment
