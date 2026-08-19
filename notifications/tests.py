"""notifications/tests.py — Full test suite for notification system."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from interactions.models import Comment, CreatorFollow, TrackLike
from tracks.models import Track

from .models import Notification
from .services import (
    check_and_notify_milestone,
    notify_comment_liked,
    notify_new_follower,
    notify_new_track_to_followers,
    notify_track_approved,
    notify_track_comment,
    notify_track_liked,
    notify_track_rejected,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(username):
    """Create a test user with completed onboarding so middleware passes."""
    u = User.objects.create_user(username=username, password="pass12345")
    # Signal auto-creates the profile; we just need to mark onboarding done
    # so OnboardingRequiredMiddleware doesn't redirect API test requests.
    u.profile.onboarding_complete = True
    u.profile.save(update_fields=["onboarding_complete"])
    return u


def _track(creator, title="Test Track", duration=300,
           status=Track.Status.DRAFT,
           visibility=Track.Visibility.PUBLIC):
    """Create a test track. Default status is DRAFT to avoid triggering
    the track_approved signal and fan-out notifications on creation.
    """
    return Track.objects.create(
        creator=creator,
        title=title,
        content_type="music",
        duration_seconds=duration,
        status=status,
        visibility=visibility,
    )


def _comment(track, author, body="خوبه!"):
    return Comment.objects.create(track=track, author=author, body=body)


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = _user("model_user")

    def test_unread_count_zero_initially(self):
        self.assertEqual(Notification.unread_count(self.user), 0)

    def test_mark_read_idempotent(self):
        n = Notification.objects.create(
            recipient=self.user,
            verb=Notification.Verb.TRACK_APPROVED,
            group_key="",
        )
        n.mark_read()
        n.mark_read()
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)

    def test_mark_all_read(self):
        creator = _user("creator_m")
        for _ in range(3):
            Notification.objects.create(
                recipient=self.user,
                verb=Notification.Verb.NEW_FOLLOWER,
                actor=creator,
                group_key="",
            )
        updated = Notification.mark_all_read(self.user)
        self.assertEqual(updated, 3)
        self.assertEqual(Notification.unread_count(self.user), 0)

    def test_persian_text_track_liked(self):
        creator = _user("creator_pt")
        liker = _user("liker_pt")
        track = _track(creator)
        n = Notification.objects.create(
            recipient=creator,
            verb=Notification.Verb.TRACK_LIKED,
            actor=liker,
            track=track,
            group_key="",
        )
        self.assertIn(track.title, n.persian_text())

    def test_persian_text_grouped_shows_count(self):
        creator = _user("creator_gr")
        liker = _user("liker_gr")
        track = _track(creator)
        n = Notification.objects.create(
            recipient=creator,
            verb=Notification.Verb.TRACK_LIKED,
            actor=liker,
            track=track,
            group_key="",
            actor_count=5,
        )
        self.assertIn("4", n.persian_text())  # "و 4 نفر دیگر"

    def test_build_group_key_format(self):
        key = Notification.build_group_key("track_liked", "track", 42)
        self.assertEqual(key, "track_liked:track:42")


# ---------------------------------------------------------------------------
# Service: notify_new_follower
# ---------------------------------------------------------------------------

class NotifyFollowerTests(TestCase):
    def setUp(self):
        self.creator = _user("creator_f")
        self.follower = _user("follower_f")

    def test_creates_notification(self):
        notify_new_follower(follower=self.follower, creator=self.creator)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.NEW_FOLLOWER,
            ).count(), 1
        )

    def test_self_follow_ignored(self):
        notify_new_follower(follower=self.creator, creator=self.creator)
        self.assertEqual(Notification.objects.count(), 0)

    def test_multiple_followers_grouped(self):
        for i in range(3):
            f = _user(f"follower_g{i}")
            notify_new_follower(follower=f, creator=self.creator)
        notifs = Notification.objects.filter(recipient=self.creator)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().actor_count, 3)


# ---------------------------------------------------------------------------
# Service: notify_track_liked
# ---------------------------------------------------------------------------

class NotifyTrackLikedTests(TestCase):
    def setUp(self):
        self.creator = _user("creator_l")
        self.liker = _user("liker_l")
        self.track = _track(self.creator)

    def test_creates_notification(self):
        notify_track_liked(liker=self.liker, track=self.track)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.TRACK_LIKED,
            ).exists()
        )

    def test_self_like_ignored(self):
        notify_track_liked(liker=self.creator, track=self.track)
        self.assertEqual(Notification.objects.count(), 0)

    def test_grouped_within_window(self):
        for i in range(4):
            liker = _user(f"liker_gw{i}")
            notify_track_liked(liker=liker, track=self.track)
        self.assertEqual(
            Notification.objects.filter(recipient=self.creator).count(), 1
        )
        self.assertEqual(
            Notification.objects.get(recipient=self.creator).actor_count, 4
        )

    def test_new_row_after_window_expires(self):
        old = Notification.objects.create(
            recipient=self.creator,
            verb=Notification.Verb.TRACK_LIKED,
            actor=self.liker,
            track=self.track,
            group_key=f"track_liked:track:{self.track.pk}",
            is_read=False,
        )
        Notification.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        new_liker = _user("liker_after_window")
        notify_track_liked(liker=new_liker, track=self.track)
        self.assertEqual(
            Notification.objects.filter(recipient=self.creator).count(), 2
        )

    def test_read_notification_triggers_new_row(self):
        Notification.objects.create(
            recipient=self.creator,
            verb=Notification.Verb.TRACK_LIKED,
            actor=self.liker,
            track=self.track,
            group_key=f"track_liked:track:{self.track.pk}",
            is_read=True,
        )
        new_liker = _user("liker_after_read")
        notify_track_liked(liker=new_liker, track=self.track)
        self.assertEqual(
            Notification.objects.filter(recipient=self.creator).count(), 2
        )


# ---------------------------------------------------------------------------
# Service: notify_track_comment
# ---------------------------------------------------------------------------

class NotifyCommentTests(TestCase):
    def setUp(self):
        self.creator = _user("creator_c")
        self.commenter = _user("commenter_c")
        self.track = _track(self.creator)

    def test_creates_notification(self):
        comment = _comment(self.track, self.commenter)
        notify_track_comment(
            commenter=self.commenter, track=self.track, comment=comment
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.TRACK_COMMENT,
            ).exists()
        )

    def test_self_comment_ignored(self):
        comment = _comment(self.track, self.creator)
        notify_track_comment(
            commenter=self.creator, track=self.track, comment=comment
        )
        self.assertEqual(Notification.objects.count(), 0)


# ---------------------------------------------------------------------------
# Service: notify_comment_liked
# ---------------------------------------------------------------------------

class NotifyCommentLikedTests(TestCase):
    def setUp(self):
        self.creator = _user("creator_cl")
        self.author = _user("author_cl")
        self.liker = _user("liker_cl")
        self.track = _track(self.creator)
        self.comment = _comment(self.track, self.author)

    def test_creates_notification(self):
        notify_comment_liked(liker=self.liker, comment=self.comment)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.author,
                verb=Notification.Verb.COMMENT_LIKED,
            ).exists()
        )

    def test_self_like_ignored(self):
        # comment creation itself may fire a notification (signal).
        # We only care that NO comment_liked notification exists.
        notify_comment_liked(liker=self.author, comment=self.comment)
        self.assertFalse(
            Notification.objects.filter(
                verb=Notification.Verb.COMMENT_LIKED
            ).exists()
        )


# ---------------------------------------------------------------------------
# Service: system notifications
# ---------------------------------------------------------------------------

class SystemNotificationTests(TestCase):
    def setUp(self):
        self.creator = _user("creator_sys")
        self.track = _track(self.creator)

    def test_track_approved(self):
        notify_track_approved(track=self.track)
        n = Notification.objects.get(recipient=self.creator)
        self.assertEqual(n.verb, Notification.Verb.TRACK_APPROVED)
        self.assertIsNone(n.actor)
        self.assertEqual(n.group_key, "")

    def test_track_rejected_with_reason(self):
        notify_track_rejected(track=self.track, reason="کپی‌رایت")
        n = Notification.objects.get(recipient=self.creator)
        self.assertEqual(n.verb, Notification.Verb.TRACK_REJECTED)
        self.assertEqual(n.extra["reason"], "کپی‌رایت")

    def test_track_rejected_no_reason(self):
        notify_track_rejected(track=self.track)
        n = Notification.objects.get(recipient=self.creator)
        self.assertEqual(n.extra.get("reason", ""), "")


# ---------------------------------------------------------------------------
# Service: fan-out to followers
# ---------------------------------------------------------------------------

class FanOutTests(TestCase):
    def setUp(self):
        self.creator = _user("creator_fo")
        self.f1 = _user("follower_fo1")
        self.f2 = _user("follower_fo2")
        self.track = _track(self.creator)
        CreatorFollow.objects.create(user=self.f1, creator=self.creator)
        CreatorFollow.objects.create(user=self.f2, creator=self.creator)

    def test_all_followers_notified(self):
        notify_new_track_to_followers(track=self.track)
        self.assertEqual(
            Notification.objects.filter(
                verb=Notification.Verb.NEW_TRACK_FROM_FOLLOW
            ).count(), 2
        )

    def test_correct_recipients(self):
        notify_new_track_to_followers(track=self.track)
        recipients = set(
            Notification.objects.filter(
                verb=Notification.Verb.NEW_TRACK_FROM_FOLLOW
            ).values_list("recipient_id", flat=True)
        )
        self.assertEqual(recipients, {self.f1.pk, self.f2.pk})

    def test_creator_not_notified_of_own_track(self):
        notify_new_track_to_followers(track=self.track)
        # Creator should NOT receive a NEW_TRACK_FROM_FOLLOW notification
        # (they may have other notifications e.g. new_follower from setUp)
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.NEW_TRACK_FROM_FOLLOW,
            ).exists()
        )

    def test_no_followers_no_error(self):
        CreatorFollow.objects.all().delete()
        notify_new_track_to_followers(track=self.track)
        self.assertFalse(
            Notification.objects.filter(
                verb=Notification.Verb.NEW_TRACK_FROM_FOLLOW
            ).exists()
        )


# ---------------------------------------------------------------------------
# Service: milestone
# ---------------------------------------------------------------------------

class MilestoneTests(TestCase):
    def setUp(self):
        self.creator = _user("creator_ms")
        self.track = _track(self.creator)

    def test_milestone_100(self):
        Track.objects.filter(pk=self.track.pk).update(play_count=100)
        self.track.refresh_from_db()
        check_and_notify_milestone(track=self.track)
        n = Notification.objects.get(
            recipient=self.creator, verb=Notification.Verb.MILESTONE_PLAYS
        )
        self.assertEqual(n.extra["milestone"], 100)

    def test_milestone_idempotent(self):
        Track.objects.filter(pk=self.track.pk).update(play_count=100)
        self.track.refresh_from_db()
        check_and_notify_milestone(track=self.track)
        check_and_notify_milestone(track=self.track)
        self.assertEqual(
            Notification.objects.filter(
                verb=Notification.Verb.MILESTONE_PLAYS,
                extra__milestone=100,
            ).count(), 1
        )

    def test_multiple_milestones_at_once(self):
        Track.objects.filter(pk=self.track.pk).update(play_count=600)
        self.track.refresh_from_db()
        check_and_notify_milestone(track=self.track)
        milestones = list(
            Notification.objects.filter(
                verb=Notification.Verb.MILESTONE_PLAYS
            ).values_list("extra__milestone", flat=True)
        )
        self.assertIn(100, milestones)
        self.assertIn(500, milestones)
        self.assertNotIn(1000, milestones)

    def test_below_first_milestone_no_notification(self):
        Track.objects.filter(pk=self.track.pk).update(play_count=50)
        self.track.refresh_from_db()
        check_and_notify_milestone(track=self.track)
        self.assertEqual(Notification.objects.count(), 0)


# ---------------------------------------------------------------------------
# API views
# ---------------------------------------------------------------------------

class NotificationAPITests(TestCase):
    def setUp(self):
        self.user = _user("api_user")
        self.creator = _user("api_creator")
        self.track = _track(self.creator)
        self.client.login(username="api_user", password="pass12345")
        Notification.objects.create(
            recipient=self.user,
            verb=Notification.Verb.TRACK_APPROVED,
            track=self.track,
            group_key="",
        )

    def test_api_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("api_notifications"))
        self.assertEqual(resp.status_code, 302)

    def test_api_returns_json(self):
        resp = self.client.get(reverse("api_notifications"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["unread_count"], 1)
        self.assertEqual(len(data["notifications"]), 1)

    def test_mark_all_read(self):
        resp = self.client.post(reverse("api_notifications_read"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["unread_count"], 0)

    def test_mark_one_read(self):
        notif = Notification.objects.filter(recipient=self.user).first()
        resp = self.client.post(
            reverse("api_notifications_read"),
            {"notification_id": notif.pk},
        )
        self.assertEqual(resp.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_read_wrong_user_404(self):
        other = _user("other_api")
        notif = Notification.objects.create(
            recipient=other,
            verb=Notification.Verb.TRACK_APPROVED,
            group_key="",
        )
        resp = self.client.post(
            reverse("api_notifications_read"),
            {"notification_id": notif.pk},
        )
        self.assertEqual(resp.status_code, 404)

    def test_list_view_renders(self):
        resp = self.client.get(reverse("notification_list"))
        self.assertEqual(resp.status_code, 200)

    def test_mark_read_get_not_allowed(self):
        resp = self.client.get(reverse("api_notifications_read"))
        self.assertEqual(resp.status_code, 405)


# ---------------------------------------------------------------------------
# Signal integration
# ---------------------------------------------------------------------------

class SignalIntegrationTests(TestCase):
    def setUp(self):
        self.creator = _user("sig_creator")
        self.follower = _user("sig_follower")
        self.track = _track(self.creator, status=Track.Status.DRAFT)

    def test_follow_signal_creates_notification(self):
        CreatorFollow.objects.create(user=self.follower, creator=self.creator)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.NEW_FOLLOWER,
            ).exists()
        )

    def test_like_signal_creates_notification(self):
        TrackLike.objects.create(user=self.follower, track=self.track)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.TRACK_LIKED,
            ).exists()
        )

    def test_comment_signal_creates_notification(self):
        Comment.objects.create(
            track=self.track, author=self.follower, body="عالیه!"
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.TRACK_COMMENT,
            ).exists()
        )

    def test_track_approved_signal(self):
        self.track.status = Track.Status.APPROVED
        self.track.save(update_fields=["status"])
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.TRACK_APPROVED,
            ).exists()
        )

    def test_track_rejected_signal_with_reason(self):
        self.track.status = Track.Status.REJECTED
        self.track.reject_reason = "محتوای نامناسب"
        self.track.save(update_fields=["status", "reject_reason"])
        n = Notification.objects.get(
            recipient=self.creator,
            verb=Notification.Verb.TRACK_REJECTED,
        )
        self.assertEqual(n.extra["reason"], "محتوای نامناسب")

    def test_self_like_does_not_notify(self):
        TrackLike.objects.create(user=self.creator, track=self.track)
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.creator,
                verb=Notification.Verb.TRACK_LIKED,
            ).exists()
        )
