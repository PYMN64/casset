from django.urls import path

from core import views

urlpatterns = [
    path("healthz/", views.health_check, name="health_check"),
]
