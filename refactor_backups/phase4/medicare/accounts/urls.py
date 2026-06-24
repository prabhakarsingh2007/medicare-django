from django.urls import path
from .views import (
    register_view,
    verify_otp_view,
    complete_registration_view,
    complete_profile_view,
    login_view,
    logout_view,
    patient_profile,
    select_hospital,
)

urlpatterns = [
    path('register/', register_view, name='register'),
    path('verify-otp/', verify_otp_view, name='verify_otp'),
    path('complete-registration/', complete_registration_view, name='complete_registration'),
    path('complete-profile/', complete_profile_view, name='complete_profile'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path("patient_profile/", patient_profile, name="patient_profile"),
    path("select_hospital/<slug:slug>/", select_hospital, name="select_hospital"),
]
