from .models import ActivityLog, Doctor, HospitalAdminProfile


def resolve_actor_role(user):
    if not user or not user.is_authenticated:
        return "system"
    if user.is_superuser:
        return "superadmin"
    if HospitalAdminProfile.objects.filter(user=user, is_active=True).exists():
        return "hospital_admin"
    if Doctor.objects.filter(user=user).exists():
        return "doctor"
    return "patient"


def log_activity(actor, action, target_type, target_id=None, description="", extra_data=None):
    ActivityLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_role=resolve_actor_role(actor),
        action=action,
        target_type=target_type,
        target_id=target_id,
        description=description,
        extra_data=extra_data or {},
    )
