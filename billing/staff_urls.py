from django.urls import path

from . import staff_views

urlpatterns = [
    path("payouts/", staff_views.payout_queue, name="staff_payout_queue"),
    path("payouts/<int:payout_id>/approve/", staff_views.approve_payout, name="staff_approve_payout"),
    path("payouts/<int:payout_id>/reject/", staff_views.reject_payout, name="staff_reject_payout"),
]
