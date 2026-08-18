from django.urls import path
from . import views

urlpatterns = [
    path("vip/", views.vip_page, name="vip"),
    path("vip/activate-dev/", views.activate_vip_dev, name="vip_activate_dev"),
    path("vip/activate-dev/<int:plan_id>/", views.activate_vip_dev, name="vip_activate_dev_plan"),
    path("payout/", views.payout_page, name="payout"),
    path("payout/request/", views.create_payout_request, name="create_payout_request"),
]
