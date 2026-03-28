
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from careapp.views import *
from careapp.admin_view import *


urlpatterns = [
    path('superadmin/', admin.site.urls),
    path("", home , name="home"),
    path("specialist_doctors/<int:id>/", specialist_doctors, name="specialist_doctors"),
    path("select_hospital/<slug:slug>/", select_hospital, name="select_hospital"),
    path("book_appointment/<slug:slug>/", book_appointment, name='book_appointment'),
    path("booked_slots/", get_booked_slots, name='booked_slots'),
    path("edit_appointment/<int:id>/", edit_appointment, name="edit_appointment"),
    path("cancel_appointment/<int:id>/", cancel_appointment, name="cancel_appointment"),
    # admin routes
    path("admin/", dashboard, name='admin-dashboard'),
    path("admin/view_doctor", view_doctor, name="view_doctor"),
    path("admin/view_patient", view_patient, name="view_patient"),
    path("admin/view_appoinment", view_appointment, name="view_appointment"),
    path("payment/<int:id>/", payment, name="payment"),
    path("successfull/",successfull_payment,name="successful_payment"),
    path("doctor_dashboard/", doctor_dashboard, name="doctor_dashboard"),
    path("doctor/appointment/<int:id>/status/<str:status>/", doctor_update_appointment_status, name="doctor_update_appointment_status"),
    path("doctor/appointment/<int:id>/reschedule/", doctor_reschedule_appointment, name="doctor_reschedule_appointment"),
    path('delete_doctor/<int:pk>/', delete_doctor, name='delete_doctor'),
    path('edit_doctor/<int:pk>/', edit_doctor, name='edit_doctor'),
    path('delete_specialist/<int:pk>/', delete_specialist, name='delete_specialist'),
    path("doctor_profile/<slug:slug>/", doctor_profile, name="doctor_profile"),
    path("patient_dashboard/", patient_dashboard, name="patient_dashboard"),
    path("patient_profile/", patient_profile, name="patient_profile"),
    path("patient/my_appointments", my_appointments, name="my_appointments"),
    path('register/', register_view, name='register'),
    path('verify-email/<str:token>/', verify_email, name='verify_email'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
   
   
    path('admin/add_doctor/',add_doctor, name='add_doctor'),
    path("admin/add_specialist/", add_specialist, name="add_specialist"),
    path("admin/view_specialist/", view_specialist, name="view_specialist"),
    path("admin/add_hospital/", add_hospital, name="add_hospital"),
    path("admin/add_hospital_admin/", add_hospital_admin, name="add_hospital_admin"),
    path("admin/view_hospital_admins/", view_hospital_admins, name="view_hospital_admins"),
    path("admin/toggle_hospital_admin_status/<int:pk>/", toggle_hospital_admin_status, name="toggle_hospital_admin_status"),
    path("admin/reset_hospital_admin_password/<int:pk>/", reset_hospital_admin_password, name="reset_hospital_admin_password"),
    path("admin/change_password/", change_admin_password, name="change_admin_password"),
    path("admin/view_hospital/", view_hospital, name="view_hospital"),
    path("delete_hospital/<int:pk>/", delete_hospital, name='delete_hospital'),

    #extra


    
    path("about/", about, name="about"),
    path("contact/", contact, name="contact"),



    


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
