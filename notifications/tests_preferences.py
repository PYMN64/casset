"""notifications/tests_preferences.py — per-user notification opt-outs.

The whole point of the preference model is that switching something off
actually stops the row being written, rather than filtering a feed that
keeps growing. These tests assert that, and assert the two verbs that must
never be suppressible really are not.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.test_utils import make_user
from tracks.models import Track

from .models import Notification, NotificationPreference
from .services import (
    notify_new_follower,
    notify_track_approved,
    notify_track_liked,
    notify_track_rejected,
)

User = get_user_model()


class NotificationPreferenceTests(TestCase):
    def setUp(self):
        self.creator = make_user("pref_creator")
        self.actor = make_user("pref_actor")
        self.track = Track.objects.create(
            creator=self.creator, title="Song", content_type="music",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
        )

    def _unread(self, verb=None):
        qs = Notification.objects.filter(recipient=self.creator)
        if verb:
            qs = qs.filter(verb=verb)
        return qs.count()

    # --- defaults ---

    def test_absent_preference_row_means_everything_is_on(self):
        """Introducing this model must not silently mute existing accounts,
        so a missing row is a permissive state, not a restrictive one."""
        self.assertFalse(NotificationPreference.objects.filter(user=self.creator).exists())
        notify_track_liked(liker=self.actor, track=self.track)
        self.assertEqual(self._unread("track_liked"), 1)

    def test_reading_preferences_does_not_create_rows_on_the_hot_path(self):
        notify_track_liked(liker=self.actor, track=self.track)
        self.assertFalse(NotificationPreference.objects.filter(user=self.creator).exists())

    # --- suppression ---

    def test_switching_off_a_verb_stops_the_row_being_written(self):
        pref = NotificationPreference.for_user(self.creator)
        pref.track_liked = False
        pref.save()

        notify_track_liked(liker=self.actor, track=self.track)
        self.assertEqual(self._unread("track_liked"), 0)

    def test_switching_off_one_verb_leaves_the_others_alone(self):
        pref = NotificationPreference.for_user(self.creator)
        pref.track_liked = False
        pref.save()

        notify_track_liked(liker=self.actor, track=self.track)
        notify_new_follower(follower=self.actor, creator=self.creator)

        self.assertEqual(self._unread("track_liked"), 0)
        self.assertEqual(self._unread("new_follower"), 1)

    def test_turning_it_back_on_resumes_delivery(self):
        pref = NotificationPreference.for_user(self.creator)
        pref.track_liked = False
        pref.save()
        notify_track_liked(liker=self.actor, track=self.track)

        pref.track_liked = True
        pref.save()
        other = make_user("pref_actor2")
        notify_track_liked(liker=other, track=self.track)

        self.assertEqual(self._unread("track_liked"), 1)

    # --- always-on verbs ---

    def test_moderation_outcomes_cannot_be_muted(self):
        """Approval and rejection are consequences the creator has to see;
        letting someone mute them would make the product dishonest."""
        pref = NotificationPreference.for_user(self.creator)
        for field in NotificationPreference.VERB_FIELDS.values():
            setattr(pref, field, False)
        pref.save()

        notify_track_approved(track=self.track)
        notify_track_rejected(track=self.track, reason="کیفیت پایین")

        self.assertEqual(self._unread("track_approved"), 1)
        self.assertEqual(self._unread("track_rejected"), 1)

    def test_opt_out_applies_to_a_recipient_object_loaded_before_the_row(self):
        """Regression: the gate used to read recipient.notification_preference,
        a reverse OneToOne whose "no row" result Django caches on the
        instance. A recipient loaded before the preference existed was then
        answered from that stale cache and the opt-out was ignored — which
        is precisely the shape a real request takes when the user saves
        settings and something notifies them moments later.
        """
        stale = User.objects.get(pk=self.creator.pk)
        # Prime the descriptor cache while no row exists.
        self.assertIsNone(getattr(stale, "notification_preference", None))

        pref = NotificationPreference.for_user(self.creator)
        pref.track_liked = False
        pref.save()

        notify_track_liked(liker=self.actor, track=self.track)
        self.assertEqual(self._unread("track_liked"), 0)

    def test_allows_reports_true_for_unknown_verbs(self):
        """A verb added later must default to delivered, not silently
        dropped because nobody remembered to add a field for it."""
        pref = NotificationPreference.for_user(self.creator)
        self.assertTrue(pref.allows("some_future_verb"))


class NotificationSettingsFormTests(TestCase):
    def setUp(self):
        self.user = make_user("pref_form_user")
        self.client.login(username="pref_form_user", password="pass12345")

    def test_settings_page_renders_a_switch_per_preference(self):
        resp = self.client.get(reverse_settings())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode().count('class="switch"'), 8)

    def test_saving_the_form_persists_the_opt_out(self):
        resp = self.client.post(reverse_settings(), {
            "section": "notifications",
            # Everything omitted is unchecked; send only one field on.
            "new_follower": "on",
        })
        self.assertEqual(resp.status_code, 302)

        pref = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(pref.new_follower)
        self.assertFalse(pref.track_liked)
        self.assertFalse(pref.weekly_email_digest)

    def test_saved_opt_out_actually_suppresses_a_later_notification(self):
        """End to end: the switch in the UI reaches the enforcement point."""
        self.client.post(reverse_settings(), {"section": "notifications"})

        actor = make_user("pref_form_actor")
        notify_new_follower(follower=actor, creator=self.user)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 0)


def reverse_settings():
    from django.urls import reverse

    return reverse("settings")
