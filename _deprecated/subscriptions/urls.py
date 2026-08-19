from django.urls import path

from . import views

urlpatterns = [
    path("vip/", views.vip_page, name="vip_page"),
    path("vip/activate-dev/", views.activate_vip_dev, name="vip_activate_dev"),
]
