from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
import io

from core.models import PlatformSetting
from core.test_utils import make_user
from .models import Album, Track
from .forms import AlbumForm

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
