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
    path("book_appointment/<slug:slug>/", book_appointment, name='book_appointment'),
    # admin routes
    path("admin/", dashboard, name='admin-dashboard'),
    path("admin/view_doctor", view_doctor, name="view_doctor"),
    path("admin/view_patient", view_patient, name="view_patient"),
    path("admin/view_appoinment", view_appointment, name="view_appointment"),
    path("payment/<int:id>/", payment, name="payment"),
    path("successfull/",successfull_payment,name="successful_payment"),
    path("doctor_dashboard/", doctor_dashboard, name="doctor_dashboard"),
    path("patient_dashboard/", patient_dashboard, name="patient_dashboard"),
    path("patient_profile/", patient_profile, name="patient_profile"),
    path("patient/my_appointments", my_appointments, name="my_appointments"),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
   
   
    path('admin/add_doctor/',add_doctor, name='add_doctor'),
    path("admin/add_specialist/", add_specialist, name="add_specialist"),
    path("admin/view_specialist/", view_specialist, name="view_specialist"),

    # Ambulance
    path("admin/ambulance_list/", ambulance_list, name="ambulance_list"),
    path("ambulance_booking/", ambulance_booking, name="ambulance_booking"),
    path("admin/add_ambulance/", add_ambulance, name="add_ambulance"),
    path("admin/ambulance_booked/", all_ambulance_booked, name="all_ambulance_booked"), 


# Lab
    path("admin/add_lab_test/", add_lab_test, name="add_lab_test"),
    path("admin/lab_test_list/", lab_test_list, name="lab_test_list"),
    path("lab_booking/", lab_booking, name="lab_booking"),
    path("admin/lab_booked/", all_lab_booked, name="all_lab_booked"),

# Medicine
    path("admin/medicine_list/", medicine_list, name="medicine_list"),
    path("medicine_order/", medicine_order, name="medicine_order"),
    path("admin/add_medicine/", add_medicine, name="add_medicine"),
    path("admin/all_medicine_ordered/", all_medicine_ordered, name="all_medicine_ordered"),


    


    


   




    #extra


    
    path("about/", about, name="about"),
    path("contact/", contact, name="contact"),



    


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
