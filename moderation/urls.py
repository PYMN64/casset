from django.urls import path

from . import views

urlpatterns = [
    path('report/profile/@<str:username>/', views.report_profile, name='report_profile'),
    path('report/track/<int:track_id>/', views.report_track, name='report_track'),
    path('report/comment/<int:comment_id>/', views.report_comment, name='report_comment'),

    # Staff moderation
    path('moderation/tracks/', views.track_queue, name='moderation_track_queue'),
    path('moderation/tracks/<int:track_id>/approve/', views.approve_track, name='moderation_approve_track'),
    path('moderation/tracks/<int:track_id>/reject/', views.reject_track, name='moderation_reject_track'),
    path('moderation/reports/', views.report_queue, name='moderation_report_queue'),
    path('moderation/reports/<int:report_id>/status/', views.update_report, name='moderation_update_report'),
    path('moderation/comments/<int:comment_id>/restore/', views.restore_comment_view, name='moderation_restore_comment'),
    path('moderation/profile/@<str:username>/suspend/', views.suspend_profile, name='moderation_suspend_profile'),
    path('moderation/profile/@<str:username>/unsuspend/', views.unsuspend_profile, name='moderation_unsuspend_profile'),
]
