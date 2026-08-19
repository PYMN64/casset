from django.urls import path

from . import views

urlpatterns = [
    path('report/profile/@<str:username>/', views.report_profile, name='report_profile'),
    path('report/track/<int:track_id>/', views.report_track, name='report_track'),

    # Staff moderation
    path('moderation/tracks/', views.track_queue, name='moderation_track_queue'),
    path('moderation/tracks/<int:track_id>/approve/', views.approve_track, name='moderation_approve_track'),
    path('moderation/tracks/<int:track_id>/reject/', views.reject_track, name='moderation_reject_track'),
    path('moderation/reports/', views.report_queue, name='moderation_report_queue'),
]
