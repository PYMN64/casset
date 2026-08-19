from django.urls import path

from . import views

urlpatterns = [
    path("notifications/", views.notification_list, name="notification_list"),
    path("api/v1/notifications/", views.notification_api, name="api_notifications"),
    path("api/v1/notifications/read/", views.mark_read, name="api_notifications_read"),
]
