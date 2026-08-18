"""uploads/tests.py — Tests for the track upload/edit/submit flow.

Covers what was previously a completely empty test stub. In particular:
  * server-side file-type validation for audio/video/cover (a confirmed
    security gap: raw FileField/ImageField had zero validation before this
    session — any file type could be uploaded as "audio"),
  * ownership enforcement on edit/submit,
  * the free-minutes quota and the (previously unenforced) daily upload
    count cap.
"""

import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import PlatformSetting
from core.test_utils import make_user
from tracks.models import Track

_MEDIA_ROOT = tempfile.mkdtemp(prefix="casset-uploads-tests-")


def _make_audio_file(name="song.mp3"):
    """Minimal but structurally valid ID3v2-tagged MP3 header."""
    header = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
    return SimpleUploadedFile(name, header, content_type="audio/mpeg")


def _make_fake_audio_file(name="evil.mp3"):
    """A file renamed to .mp3 that is not actually audio."""
    return SimpleUploadedFile(name, b"<script>alert(1)</script>", content_type="audio/mpeg")


def _make_video_file(name="clip.mp4"):
    """Minimal ISO-base-media (mp4) box header."""
    header = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32
    return SimpleUploadedFile(name, header, content_type="video/mp4")


def _make_image_file(name="cover.png", fmt="PNG", size=(20, 20)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color=(10, 20, 30)).save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type=f"image/{fmt.lower()}")


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class TrackUploadFormFileValidationTests(TestCase):
    """Field-level clean_* validators on TrackUploadForm.

    These exercise core.validators.{validate_audio,validate_image,validate_video}
    through the form — the same magic-byte-not-extension rule already used by
    tracks.forms.AlbumForm.clean_cover.
    """

    def setUp(self):
        self.user = make_user("upload_form_user")
        PlatformSetting.get_solo()

    def _base_data(self, **overrides):
        data = {
            "content_type": Track.ContentType.MUSIC,
            "title": "My Track",
            "description": "",
            "language": "",
            "visibility": Track.Visibility.PUBLIC,
            "duration_minutes": 3,
            "tags_text": "",
        }
        data.update(overrides)
        return data

    def test_valid_audio_accepted(self):
        from uploads.forms import TrackUploadForm

        form = TrackUploadForm(
            self._base_data(),
            {"audio": _make_audio_file()},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_audio_file_rejected(self):
        from uploads.forms import TrackUploadForm

        form = TrackUploadForm(
            self._base_data(),
            {"audio": _make_fake_audio_file()},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("audio", form.errors)

    def test_valid_cover_accepted(self):
        from uploads.forms import TrackUploadForm

        form = TrackUploadForm(
            self._base_data(),
            {"audio": _make_audio_file(), "cover": _make_image_file()},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_image_cover_rejected(self):
        from uploads.forms import TrackUploadForm

        fake_cover = SimpleUploadedFile("cover.png", b"not an image", content_type="image/png")
        form = TrackUploadForm(
            self._base_data(),
            {"audio": _make_audio_file(), "cover": fake_cover},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("cover", form.errors)

    def test_valid_video_accepted_when_content_type_is_video(self):
        from uploads.forms import TrackUploadForm

        setting = PlatformSetting.get_solo()
        setting.enable_video = True
        setting.save(update_fields=["enable_video"])

        form = TrackUploadForm(
            self._base_data(content_type=Track.ContentType.VIDEO),
            {"video": _make_video_file()},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_video_file_rejected(self):
        from uploads.forms import TrackUploadForm

        setting = PlatformSetting.get_solo()
        setting.enable_video = True
        setting.save(update_fields=["enable_video"])

        fake_video = SimpleUploadedFile("clip.mp4", b"not a video", content_type="video/mp4")
        form = TrackUploadForm(
            self._base_data(content_type=Track.ContentType.VIDEO),
            {"video": fake_video},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("video", form.errors)

    def test_disabled_content_type_not_offered(self):
        from uploads.forms import TrackUploadForm

        setting = PlatformSetting.get_solo()
        setting.enable_video = False
        setting.save(update_fields=["enable_video"])

        form = TrackUploadForm(user=self.user)
        choice_values = [c[0] for c in form.fields["content_type"].choices]
        self.assertNotIn(Track.ContentType.VIDEO, choice_values)

    def test_disabled_content_type_rejected_even_if_posted(self):
        from uploads.forms import TrackUploadForm

        setting = PlatformSetting.get_solo()
        setting.enable_video = False
        setting.save(update_fields=["enable_video"])

        form = TrackUploadForm(
            self._base_data(content_type=Track.ContentType.VIDEO),
            {"video": _make_video_file()},
            user=self.user,
        )
        self.assertFalse(form.is_valid())


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class UploadTrackViewTests(TestCase):
    def setUp(self):
        self.user = make_user("uploader1")
        self.client.login(username="uploader1", password="pass12345")
        PlatformSetting.get_solo()

    def _post(self, **overrides):
        data = {
            "content_type": Track.ContentType.MUSIC,
            "title": "Track title",
            "description": "",
            "language": "",
            "visibility": Track.Visibility.PUBLIC,
            "duration_minutes": 3,
            "tags_text": "rock, live",
        }
        data.update(overrides)
        files = {"audio": _make_audio_file()}
        if "audio" in overrides:
            files["audio"] = overrides.pop("audio")
            data.pop("audio", None)
        return self.client.post(reverse("upload_track"), {**data, **files})

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("upload_track"))
        self.assertEqual(resp.status_code, 302)

    def test_get_renders_form(self):
        resp = self.client.get(reverse("upload_track"))
        self.assertEqual(resp.status_code, 200)

    def test_valid_upload_creates_draft_track_owned_by_user(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        track = Track.objects.get(creator=self.user)
        self.assertEqual(track.status, Track.Status.DRAFT)
        self.assertEqual(track.duration_seconds, 180)

    def test_tags_text_creates_tag_objects(self):
        self._post(tags_text="alpha, beta")
        track = Track.objects.get(creator=self.user)
        self.assertEqual({t.name for t in track.tags.all()}, {"alpha", "beta"})

    def test_fake_audio_file_rejected_no_track_created(self):
        resp = self._post(audio=_make_fake_audio_file())
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Track.objects.filter(creator=self.user).exists())

    def test_daily_upload_limit_blocks_extra_upload(self):
        setting = PlatformSetting.get_solo()
        setting.creator_daily_upload_limit = 1
        setting.save(update_fields=["creator_daily_upload_limit"])

        first = self._post()
        self.assertEqual(first.status_code, 302)

        second = self._post(title="Second track")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Track.objects.filter(creator=self.user).count(), 1)

    def test_daily_upload_limit_resets_for_different_day(self):
        setting = PlatformSetting.get_solo()
        setting.creator_daily_upload_limit = 1
        setting.save(update_fields=["creator_daily_upload_limit"])

        yesterday = timezone.now() - timezone.timedelta(days=1)
        old_track = Track.objects.create(
            creator=self.user,
            title="Old track",
            content_type=Track.ContentType.MUSIC,
            duration_seconds=60,
        )
        Track.objects.filter(pk=old_track.pk).update(created_at=yesterday)

        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Track.objects.filter(creator=self.user).count(), 2)

    def test_free_minutes_cap_blocks_upload_over_limit(self):
        setting = PlatformSetting.get_solo()
        setting.free_upload_minutes = 5
        setting.save(update_fields=["free_upload_minutes"])

        Track.objects.create(
            creator=self.user,
            title="Existing",
            content_type=Track.ContentType.MUSIC,
            duration_seconds=4 * 60,
        )

        resp = self._post(duration_minutes=5)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Track.objects.filter(creator=self.user).count(), 1)

    def test_vip_user_bypasses_free_minutes_cap(self):
        setting = PlatformSetting.get_solo()
        setting.free_upload_minutes = 5
        setting.save(update_fields=["free_upload_minutes"])

        self.user.profile.is_vip = True
        self.user.profile.save(update_fields=["is_vip"])

        Track.objects.create(
            creator=self.user,
            title="Existing",
            content_type=Track.ContentType.MUSIC,
            duration_seconds=4 * 60,
        )

        resp = self._post(duration_minutes=50)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Track.objects.filter(creator=self.user).count(), 2)

    def test_vip_user_still_subject_to_daily_upload_limit(self):
        setting = PlatformSetting.get_solo()
        setting.creator_daily_upload_limit = 1
        setting.save(update_fields=["creator_daily_upload_limit"])

        self.user.profile.is_vip = True
        self.user.profile.save(update_fields=["is_vip"])

        self._post()
        second = self._post(title="Second")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Track.objects.filter(creator=self.user).count(), 1)


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class MyTracksViewTests(TestCase):
    def setUp(self):
        self.user = make_user("owner1")
        self.other = make_user("owner2")

    def test_requires_login(self):
        resp = self.client.get(reverse("my_tracks"))
        self.assertEqual(resp.status_code, 302)

    def test_only_shows_own_tracks(self):
        Track.objects.create(creator=self.user, title="Mine", content_type=Track.ContentType.MUSIC)
        Track.objects.create(creator=self.other, title="Not mine", content_type=Track.ContentType.MUSIC)

        self.client.login(username="owner1", password="pass12345")
        resp = self.client.get(reverse("my_tracks"))
        titles = {t.title for t in resp.context["tracks"]}
        self.assertEqual(titles, {"Mine"})


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class EditTrackViewTests(TestCase):
    def setUp(self):
        self.user = make_user("editor1")
        self.other = make_user("editor2")
        self.track = Track.objects.create(
            creator=self.user,
            title="Original title",
            content_type=Track.ContentType.MUSIC,
            duration_seconds=120,
        )
        self.client.login(username="editor1", password="pass12345")
        PlatformSetting.get_solo()

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("edit_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 302)

    def test_non_owner_gets_404(self):
        self.client.logout()
        self.client.login(username="editor2", password="pass12345")
        resp = self.client.get(reverse("edit_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 404)

    def test_get_renders_prefilled_form(self):
        resp = self.client.get(reverse("edit_track", args=[self.track.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["form"].instance.pk, self.track.pk)

    def test_valid_edit_updates_owned_track(self):
        resp = self.client.post(
            reverse("edit_track", args=[self.track.id]),
            {
                "content_type": Track.ContentType.MUSIC,
                "title": "Updated title",
                "description": "",
                "language": "",
                "visibility": Track.Visibility.PUBLIC,
                "duration_minutes": 2,
                "tags_text": "",
                "audio": _make_audio_file(),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.track.refresh_from_db()
        self.assertEqual(self.track.title, "Updated title")

    def test_edit_cannot_reassign_creator_via_post(self):
        """`creator` isn't a form field; POSTing one must not change ownership."""
        resp = self.client.post(
            reverse("edit_track", args=[self.track.id]),
            {
                "content_type": Track.ContentType.MUSIC,
                "title": "Still mine",
                "description": "",
                "language": "",
                "visibility": Track.Visibility.PUBLIC,
                "duration_minutes": 2,
                "tags_text": "",
                "audio": _make_audio_file(),
                "creator": self.other.pk,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.track.refresh_from_db()
        self.assertEqual(self.track.creator_id, self.user.pk)


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class SubmitTrackViewTests(TestCase):
    def setUp(self):
        self.user = make_user("submitter1")
        self.other = make_user("submitter2")
        self.client.login(username="submitter1", password="pass12345")

    def _make_track(self, status=Track.Status.DRAFT, creator=None):
        return Track.objects.create(
            creator=creator or self.user,
            title="T",
            content_type=Track.ContentType.MUSIC,
            duration_seconds=60,
            status=status,
        )

    def test_requires_login(self):
        self.client.logout()
        track = self._make_track()
        resp = self.client.post(reverse("submit_track", args=[track.id]))
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        track = self._make_track()
        resp = self.client.get(reverse("submit_track", args=[track.id]))
        self.assertEqual(resp.status_code, 404)

    def test_non_owner_gets_404(self):
        track = self._make_track(creator=self.other)
        resp = self.client.post(reverse("submit_track", args=[track.id]))
        self.assertEqual(resp.status_code, 404)
        track.refresh_from_db()
        self.assertEqual(track.status, Track.Status.DRAFT)

    def test_draft_track_can_be_submitted(self):
        track = self._make_track(status=Track.Status.DRAFT)
        resp = self.client.post(reverse("submit_track", args=[track.id]))
        self.assertEqual(resp.status_code, 302)
        track.refresh_from_db()
        self.assertEqual(track.status, Track.Status.SUBMITTED)
        self.assertIsNotNone(track.submitted_at)

    def test_rejected_track_can_be_resubmitted_and_clears_reason(self):
        track = self._make_track(status=Track.Status.REJECTED)
        track.reject_reason = "کیفیت پایین"
        track.save(update_fields=["reject_reason"])

        resp = self.client.post(reverse("submit_track", args=[track.id]))
        self.assertEqual(resp.status_code, 302)
        track.refresh_from_db()
        self.assertEqual(track.status, Track.Status.SUBMITTED)
        self.assertEqual(track.reject_reason, "")

    def test_approved_track_cannot_be_resubmitted(self):
        track = self._make_track(status=Track.Status.APPROVED)
        resp = self.client.post(reverse("submit_track", args=[track.id]))
        self.assertEqual(resp.status_code, 302)
        track.refresh_from_db()
        self.assertEqual(track.status, Track.Status.APPROVED)

    def test_already_submitted_track_cannot_be_resubmitted_twice(self):
        track = self._make_track(status=Track.Status.SUBMITTED)

        resp = self.client.post(reverse("submit_track", args=[track.id]))
        self.assertEqual(resp.status_code, 302)
        track.refresh_from_db()
        self.assertEqual(track.status, Track.Status.SUBMITTED)
