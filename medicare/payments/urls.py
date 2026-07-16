from django.urls import path
from .views import payment, successfull_payment, failed_payment

urlpatterns = [
    path("payment/<int:id>/", payment, name="payment"),
    path("successfull/", successfull_payment, name="successful_payment"),
    path("failed/", failed_payment, name="failed_payment"),
]
