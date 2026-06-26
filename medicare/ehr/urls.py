from django.urls import path
from . import views

urlpatterns = [
    path('ehr/', views.patient_ehr_list, name='patient_ehr_list'),
    path('ehr/upload/', views.patient_ehr_upload, name='patient_ehr_upload'),
    path('doctor/patients/<int:patient_id>/ehr/', views.doctor_ehr_list, name='doctor_ehr_list'),
    path('doctor/patients/<int:patient_id>/ehr/add/', views.doctor_ehr_add, name='doctor_ehr_add'),
]
