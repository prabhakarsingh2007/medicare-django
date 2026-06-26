from django.urls import path
from .views import home, about, contact, select_hospital, hospital_detail

urlpatterns = [
    path("", home, name="home"),
    path("about/", about, name="about"),
    path("contact/", contact, name="contact"),
    path("hospital/<slug:slug>/", hospital_detail, name="hospital_detail"),
    path("select-hospital/<slug:slug>/", select_hospital, name="select_hospital"),
]
