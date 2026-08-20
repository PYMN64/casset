import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import PlatformSetting
from core.test_utils import make_user

from .forms import AlbumForm
from .models import Album, Track

User = get_user_model()


def _make_image_file(fmt="PNG", size=(100, 100), color=(255, 0, 0)):
    """Return a real uploaded-file object Django forms will accept.

    A bare BytesIO is NOT enough: Django's FileField needs an
    UploadedFile (it checks .name and .size), otherwise validation
    fails with "No file was submitted".
    """
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format=fmt)
    buf.seek(0)
    ext = "jpg" if fmt.upper() == "JPEG" else fmt.lower()
    return SimpleUploadedFile(
        f"cover.{ext}", buf.read(), content_type=f"image/{fmt.lower()}"
    )


class AlbumFormTests(TestCase):
    """Form-level unit tests for AlbumForm.

    Covers: field presence, title validation, duplicate detection,
    cover MIME/size validation, content_type platform-guard.
    """

    def setUp(self):
        self.user = make_user("creator1")

    # --- field presence ---

    def test_form_fields_match_model(self):
        form = AlbumForm(user=self.user)
        self.assertNotIn("kind", form.fields)  # old crash field must never return
        self.assertIn("content_type", form.fields)
        self.assertIn("is_public", form.fields)
        self.assertIn("cover", form.fields)

    # --- title validation ---

    def test_valid_submission_creates_album(self):
        form = AlbumForm(
            data={"content_type": Album.ContentType.MUSIC, "title": "آلبوم تست", "description": "", "is_public": True},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        album = form.save(commit=False)
        album.creator = self.user
        album.save()
        self.assertEqual(Album.objects.count(), 1)

    def test_empty_title_is_rejected(self):
        form = AlbumForm(
            data={"content_type": Album.ContentType.MUSIC, "title": "   ", "is_public": True},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_title_over_140_chars_is_rejected(self):
        form = AlbumForm(
            data={"content_type": Album.ContentType.MUSIC, "title": "a" * 141, "is_public": True},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    # --- duplicate detection ---

    def test_duplicate_title_and_type_for_same_creator_is_rejected(self):
        Album.objects.create(creator=self.user, title="تکراری", content_type=Album.ContentType.MUSIC)
        form = AlbumForm(
            data={"content_type": Album.ContentType.MUSIC, "title": "تکراری", "is_public": True},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_same_title_different_type_is_allowed(self):
        """Same title is OK if content_type differs — model allows it."""
        Album.objects.create(creator=self.user, title="مشترک", content_type=Album.ContentType.MUSIC)
        PlatformSetting.objects.update_or_create(id=1, defaults={"enable_podcast": True})
        form = AlbumForm(
            data={"content_type": Album.ContentType.PODCAST, "title": "مشترک", "is_public": True},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    # --- platform content_type guard ---

    def test_disabled_content_type_not_offered_in_choices(self):
        setting = PlatformSetting.get_solo()
        setting.enable_video = False
        setting.save()
        form = AlbumForm(user=self.user)
        allowed_values = [c[0] for c in form.fields["content_type"].choices]
        self.assertNotIn(Album.ContentType.VIDEO, allowed_values)

    def test_disabled_content_type_rejected_even_if_posted(self):
        """A crafted POST with a disabled content_type must be rejected."""
        setting = PlatformSetting.get_solo()
        setting.enable_video = False
        setting.save()
        form = AlbumForm(
            data={"content_type": Album.ContentType.VIDEO, "title": "تست ویدیو", "is_public": True},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("content_type", form.errors)

    # --- cover validation ---

    def test_valid_png_cover_accepted(self):
        img = _make_image_file("PNG")
        form = AlbumForm(
            data={"content_type": Album.ContentType.MUSIC, "title": "آلبوم کاور", "is_public": True},
            files={"cover": img},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_image_file_rejected(self):
        """A text file renamed to .jpg must not pass cover validation."""
        fake = SimpleUploadedFile(
            "evil.jpg", b"not an image at all", content_type="image/jpeg"
        )
        form = AlbumForm(
            data={"content_type": Album.ContentType.MUSIC, "title": "تست بد", "is_public": True},
            files={"cover": fake},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("cover", form.errors)


class AlbumViewTests(TestCase):
    """Integration tests for album CRUD views."""

    def setUp(self):
        self.user = make_user("creator2")
        self.other = make_user("creator3")
        self.client.login(username="creator2", password="pass12345")

    # --- auth ---

    def test_album_create_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("album_create"))
        self.assertEqual(resp.status_code, 302)

    def test_album_list_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("album_list"))
        self.assertEqual(resp.status_code, 302)

    # --- create ---

    def test_album_create_get_renders_form(self):
        resp = self.client.get(reverse("album_create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ساخت آلبوم")

    def test_album_create_post_creates_album_owned_by_user(self):
        resp = self.client.post(reverse("album_create"), {
            "content_type": Album.ContentType.MUSIC,
            "title": "آلبوم من",
            "description": "",
            "is_public": True,
        })
        self.assertEqual(resp.status_code, 302)
        album = Album.objects.get(title="آلبوم من")
        self.assertEqual(album.creator, self.user)

    # --- list ---

    def test_album_list_only_shows_own_albums(self):
        Album.objects.create(creator=self.user, title="مال من", content_type=Album.ContentType.MUSIC)
        Album.objects.create(creator=self.other, title="مال دیگری", content_type=Album.ContentType.MUSIC)
        resp = self.client.get(reverse("album_list"))
        self.assertContains(resp, "مال من")
        self.assertNotContains(resp, "مال دیگری")

    # --- edit ---

    def test_album_edit_forbidden_for_non_owner(self):
        album = Album.objects.create(creator=self.other, title="آلبوم دیگری", content_type=Album.ContentType.MUSIC)
        resp = self.client.get(reverse("album_edit", args=[album.id]))
        self.assertEqual(resp.status_code, 404)

    def test_album_edit_updates_owned_album(self):
        album = Album.objects.create(creator=self.user, title="قدیمی", content_type=Album.ContentType.MUSIC)
        resp = self.client.post(reverse("album_edit", args=[album.id]), {
            "content_type": Album.ContentType.MUSIC,
            "title": "جدید",
            "description": "",
            "is_public": True,
        })
        self.assertEqual(resp.status_code, 302)
        album.refresh_from_db()
        self.assertEqual(album.title, "جدید")

    # --- delete ---

    def test_album_delete_removes_album(self):
        album = Album.objects.create(creator=self.user, title="حذفی", content_type=Album.ContentType.MUSIC)
        resp = self.client.post(reverse("album_delete", args=[album.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Album.objects.filter(id=album.id).exists())

    def test_album_delete_forbidden_for_non_owner(self):
        album = Album.objects.create(creator=self.other, title="مال دیگری", content_type=Album.ContentType.MUSIC)
        resp = self.client.post(reverse("album_delete", args=[album.id]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Album.objects.filter(id=album.id).exists())

    def test_album_delete_get_not_allowed(self):
        """DELETE via GET must be rejected (require_POST guard)."""
        album = Album.objects.create(creator=self.user, title="دسترسی GET", content_type=Album.ContentType.MUSIC)
        resp = self.client.get(reverse("album_delete", args=[album.id]))
        self.assertEqual(resp.status_code, 405)  # Method Not Allowed
        self.assertTrue(Album.objects.filter(id=album.id).exists())

    def test_album_delete_detaches_tracks_not_deletes_them(self):
        """Deleting an album must NOT delete its tracks — only detach them."""
        album = Album.objects.create(creator=self.user, title="آلبوم با ترک", content_type=Album.ContentType.MUSIC)
        track = Track.objects.create(
            creator=self.user,
            album=album,
            title="ترک تست",
            content_type=Track.ContentType.MUSIC,
        )
        self.client.post(reverse("album_delete", args=[album.id]))
        track.refresh_from_db()
        self.assertIsNone(track.album)  # detached, not deleted
        self.assertTrue(Track.objects.filter(id=track.id).exists())


# ---------------------------------------------------------------------------
# Open Graph / meta tags (track_detail)
# ---------------------------------------------------------------------------

class TrackDetailOpenGraphTests(TestCase):
    def setUp(self):
        self.creator = make_user("og_creator")
        self.track = Track.objects.create(
            creator=self.creator, title="Test Track Title", description="توضیحات ترک",
            content_type=Track.ContentType.MUSIC,
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
        )

    def test_og_title_and_description_present(self):
        resp = self.client.get(reverse("track_detail", args=[self.track.slug]))
        self.assertContains(resp, 'property="og:title"')
        self.assertContains(resp, "Test Track Title")
        self.assertContains(resp, 'property="og:description"')
        self.assertContains(resp, "توضیحات ترک")

    def test_no_og_image_without_cover(self):
        resp = self.client.get(reverse("track_detail", args=[self.track.slug]))
        self.assertNotContains(resp, 'property="og:image"')

    def test_og_image_present_with_cover(self):
        self.track.cover = _make_image_file()
        self.track.save()
        resp = self.client.get(reverse("track_detail", args=[self.track.slug]))
        self.assertContains(resp, 'property="og:image"')
        self.assertContains(resp, self.track.cover.url)


# ---------------------------------------------------------------------------
# Persian (non-ASCII) slugs
#
# Track.save() slugifies with allow_unicode=True, so a Persian title yields a
# Persian slug. The URL pattern used Django's built-in `slug` converter,
# which is ASCII-only — so every Persian-titled track's detail page was
# unreachable and {% url 'track_detail' %} raised NoReverseMatch. On a
# Persian platform that is nearly all real content. Every pre-existing test
# here used ASCII titles, which is exactly why it stayed hidden.
# ---------------------------------------------------------------------------

class PersianSlugRoutingTests(TestCase):
    def setUp(self):
        self.creator = make_user("fa_slug_creator")
        self.track = Track.objects.create(
            creator=self.creator, title="رویای نیمه‌شب",
            content_type=Track.ContentType.MUSIC,
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
        )

    def test_slug_is_persian(self):
        self.assertTrue(any("؀" <= ch <= "ۿ" for ch in self.track.slug))

    def test_reverse_builds_url_for_persian_slug(self):
        """reverse() must not raise NoReverseMatch. The slug arrives
        percent-encoded in the path, which is correct URL behaviour."""
        from urllib.parse import quote

        url = reverse("track_detail", args=[self.track.slug])
        self.assertIn(quote(self.track.slug), url)

    def test_detail_page_loads_for_persian_slug(self):
        resp = self.client.get(reverse("track_detail", args=[self.track.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "رویای نیمه‌شب")

    def test_ascii_slug_still_works(self):
        ascii_track = Track.objects.create(
            creator=self.creator, title="Plain ASCII Title",
            content_type=Track.ContentType.MUSIC,
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
        )
        resp = self.client.get(reverse("track_detail", args=[ascii_track.slug]))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Waveform peak extraction (tracks/audio_processing.py)
# ---------------------------------------------------------------------------

def _make_real_wav_file(name="tone.wav", seconds=1, freq=440, samplerate=8000):
    """A genuinely decodable WAV — a sine wave written with the stdlib
    `wave` module. Unlike the ID3-header-only fixtures elsewhere in this
    file (fine for MIME-sniffing tests), waveform extraction needs audio
    soundfile can actually decode."""
    import math
    import struct
    import wave as wave_module

    buf = io.BytesIO()
    with wave_module.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        n_samples = seconds * samplerate
        frames = b"".join(
            struct.pack("<h", int(32767 * math.sin(2 * math.pi * freq * i / samplerate)))
            for i in range(n_samples)
        )
        w.writeframes(frames)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="audio/wav")


class ExtractWaveformPeaksTests(TestCase):
    def test_real_audio_returns_normalized_peaks(self):
        from .audio_processing import extract_waveform_peaks

        wav = _make_real_wav_file()
        peaks = extract_waveform_peaks(wav, num_points=50)
        self.assertEqual(len(peaks), 50)
        self.assertAlmostEqual(max(peaks), 1.0, places=2)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in peaks))

    def test_garbage_input_returns_empty_list(self):
        from .audio_processing import extract_waveform_peaks

        garbage = io.BytesIO(b"not audio data at all")
        self.assertEqual(extract_waveform_peaks(garbage), [])

    def test_silence_does_not_divide_by_zero(self):
        from .audio_processing import extract_waveform_peaks

        buf = io.BytesIO()
        import wave as wave_module
        with wave_module.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\x00\x00" * 8000)
        buf.seek(0)
        peaks = extract_waveform_peaks(buf, num_points=20)
        self.assertEqual(peaks, [0.0] * 20)


class GenerateWaveformTaskTests(TestCase):
    def setUp(self):
        self.creator = make_user("waveform_creator")

    def test_task_populates_peaks_for_real_audio(self):
        from .tasks import generate_waveform_task

        track = Track.objects.create(
            creator=self.creator, title="Tone", content_type="music",
            audio=_make_real_wav_file(),
        )
        self.assertEqual(track.waveform_peaks, [])
        generate_waveform_task(track_id=track.id)
        track.refresh_from_db()
        self.assertGreater(len(track.waveform_peaks), 0)

    def test_task_is_a_noop_for_track_without_audio(self):
        from .tasks import generate_waveform_task

        track = Track.objects.create(creator=self.creator, title="No audio", content_type="music")
        generate_waveform_task(track_id=track.id)  # must not raise
        track.refresh_from_db()
        self.assertEqual(track.waveform_peaks, [])

    def test_task_handles_missing_track_silently(self):
        from .tasks import generate_waveform_task

        generate_waveform_task(track_id=999999)  # must not raise


# ---------------------------------------------------------------------------
# Embed widget
# ---------------------------------------------------------------------------

class TrackEmbedViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("embed_creator")
        self.track = Track.objects.create(
            creator=self.creator, title="Embed Me", content_type="music",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
            audio=_make_real_wav_file(),
        )

    def test_embed_page_loads(self):
        resp = self.client.get(reverse("track_embed", args=[self.track.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Embed Me")

    def test_embed_has_no_xframe_options_header(self):
        resp = self.client.get(reverse("track_embed", args=[self.track.slug]))
        self.assertNotIn("X-Frame-Options", resp)

    def test_regular_track_page_still_blocks_framing(self):
        resp = self.client.get(reverse("track_detail", args=[self.track.slug]))
        self.assertIn("X-Frame-Options", resp)

    def test_private_track_embed_404s(self):
        private = Track.objects.create(
            creator=self.creator, title="Secret", content_type="music",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PRIVATE,
        )
        resp = self.client.get(reverse("track_embed", args=[private.slug]))
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# can_download regression (tracks/views.py::track_detail)
#
# The template gated the download button on {% if can_download %}, but the
# view never put that key in the context — so the download button never
# rendered for anyone, VIP or not, even though uploads.views.download_track
# itself worked fine if a user found the URL some other way.
# ---------------------------------------------------------------------------

class CanDownloadRegressionTests(TestCase):
    def setUp(self):
        self.creator = make_user("dl_creator")
        self.track = Track.objects.create(
            creator=self.creator, title="Downloadable", content_type="music",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
            audio=_make_real_wav_file(),
        )

    def test_non_vip_user_sees_no_download_button(self):
        make_user("dl_listener_free")
        self.client.login(username="dl_listener_free", password="pass12345")
        resp = self.client.get(reverse("track_detail", args=[self.track.slug]))
        self.assertFalse(resp.context["can_download"])
        self.assertNotContains(resp, "دانلود")

    def test_vip_user_sees_download_button(self):
        from billing.models import Invoice, Plan

        listener = make_user("dl_listener_vip")
        plan = Plan.objects.create(code="vip", title="VIP", price=0, duration_days=30)
        inv = Invoice.objects.create(user=listener, plan=plan, amount=0)
        inv.mark_paid()

        self.client.login(username="dl_listener_vip", password="pass12345")
        resp = self.client.get(reverse("track_detail", args=[self.track.slug]))
        self.assertTrue(resp.context["can_download"])
        self.assertContains(resp, "دانلود")


# ---------------------------------------------------------------------------
# Show detail + podcast RSS feed (tracks/feeds.py)
# ---------------------------------------------------------------------------

class ShowDetailViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("show_creator")
        self.album = Album.objects.create(
            creator=self.creator, title="My Podcast", content_type=Album.ContentType.PODCAST,
            is_public=True,
        )
        self.episode = Track.objects.create(
            creator=self.creator, title="Episode 1", content_type="podcast", album=self.album,
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
            audio=_make_real_wav_file(), duration_seconds=125,
        )

    def test_public_show_page_loads_with_episode(self):
        resp = self.client.get(reverse("show_detail", args=[self.album.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My Podcast")
        self.assertContains(resp, "Episode 1")

    def test_rss_link_shown_for_podcast(self):
        resp = self.client.get(reverse("show_detail", args=[self.album.id]))
        self.assertContains(resp, reverse("show_rss", args=[self.album.id]))

    def test_private_show_404s_for_stranger(self):
        self.album.is_public = False
        self.album.save(update_fields=["is_public"])
        resp = self.client.get(reverse("show_detail", args=[self.album.id]))
        self.assertEqual(resp.status_code, 404)

    def test_private_show_visible_to_owner(self):
        self.album.is_public = False
        self.album.save(update_fields=["is_public"])
        self.client.login(username="show_creator", password="pass12345")
        resp = self.client.get(reverse("show_detail", args=[self.album.id]))
        self.assertEqual(resp.status_code, 200)

    def test_draft_episode_not_listed(self):
        Track.objects.create(
            creator=self.creator, title="Unpublished", content_type="podcast", album=self.album,
            status=Track.Status.DRAFT,
        )
        resp = self.client.get(reverse("show_detail", args=[self.album.id]))
        self.assertNotContains(resp, "Unpublished")


class ShowRSSFeedTests(TestCase):
    def setUp(self):
        self.creator = make_user("rss_creator")
        self.album = Album.objects.create(
            creator=self.creator, title="RSS Show", content_type=Album.ContentType.PODCAST,
            is_public=True, description="A show about testing.",
        )
        self.episode = Track.objects.create(
            creator=self.creator, title="RSS Episode", content_type="podcast", album=self.album,
            status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
            audio=_make_real_wav_file(), duration_seconds=90, explicit=False,
        )

    def test_feed_is_valid_rss_with_itunes_namespace(self):
        resp = self.client.get(reverse("show_rss", args=[self.album.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/rss+xml; charset=utf-8")
        body = resp.content.decode()
        self.assertIn("xmlns:itunes=", body)
        self.assertIn("<title>RSS Show</title>", body)

    def test_feed_includes_episode_with_enclosure(self):
        resp = self.client.get(reverse("show_rss", args=[self.album.id]))
        body = resp.content.decode()
        self.assertIn("RSS Episode", body)
        self.assertIn("<enclosure", body)
        self.assertIn("audio/mpeg", body)

    def test_feed_excludes_non_podcast_album(self):
        music_album = Album.objects.create(
            creator=self.creator, title="Music Album", content_type=Album.ContentType.MUSIC,
            is_public=True,
        )
        resp = self.client.get(reverse("show_rss", args=[music_album.id]))
        self.assertEqual(resp.status_code, 404)

    def test_feed_404s_for_private_show(self):
        self.album.is_public = False
        self.album.save(update_fields=["is_public"])
        resp = self.client.get(reverse("show_rss", args=[self.album.id]))
        self.assertEqual(resp.status_code, 404)

    def test_feed_excludes_unapproved_episodes(self):
        Track.objects.create(
            creator=self.creator, title="Still In Review", content_type="podcast", album=self.album,
            status=Track.Status.SUBMITTED,
        )
        resp = self.client.get(reverse("show_rss", args=[self.album.id]))
        self.assertNotContains(resp, "Still In Review")
