"""core/tests_thumbnails.py — thumbnail_url template filter.

Named tests_thumbnails.py (not tests.py) to keep core/tests.py focused on
health/backup/staff; both are picked up by Django's test runner (matches
test*.py) the same way core/tests_smoke.py already is.
"""

import io

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from core.templatetags.thumbnails import thumbnail_url
from core.test_utils import make_user
from tracks.models import Track


def _make_image_file(size=(600, 600)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=(200, 50, 50)).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile("cover.png", buf.read(), content_type="image/png")


class ThumbnailUrlFilterTests(TestCase):
    def setUp(self):
        self.creator = make_user("thumb_creator")
        self.track = Track.objects.create(
            creator=self.creator, title="Thumb Track", content_type=Track.ContentType.MUSIC,
        )

    def tearDown(self):
        # Clean up generated files from local FileSystemStorage so repeated
        # test runs don't accumulate media/ cruft.
        if self.track.cover:
            for name in [self.track.cover.name, self._derived_name()]:
                if name and default_storage.exists(name):
                    default_storage.delete(name)

    def _derived_name(self):
        base = self.track.cover.name.rsplit(".", 1)[0]
        return f"{base}_thumb_300x300.jpg"

    def test_empty_field_returns_empty_string(self):
        self.assertEqual(thumbnail_url(self.track.cover, "300x300"), "")

    def test_generates_and_returns_derived_url(self):
        self.track.cover = _make_image_file()
        self.track.save()

        url = thumbnail_url(self.track.cover, "300x300")
        self.assertIn("_thumb_300x300.jpg", url)
        self.assertTrue(default_storage.exists(self._derived_name()))

    def test_derived_image_is_resized(self):
        self.track.cover = _make_image_file(size=(1200, 1200))
        self.track.save()

        thumbnail_url(self.track.cover, "300x300")
        with default_storage.open(self._derived_name(), "rb") as f:
            img = Image.open(f)
            img.load()
            self.assertLessEqual(img.width, 300)
            self.assertLessEqual(img.height, 300)

    def test_second_call_reuses_cached_file_not_regenerated(self):
        self.track.cover = _make_image_file()
        self.track.save()

        thumbnail_url(self.track.cover, "300x300")
        derived_name = self._derived_name()
        mtime_1 = default_storage.get_modified_time(derived_name)

        thumbnail_url(self.track.cover, "300x300")
        mtime_2 = default_storage.get_modified_time(derived_name)
        self.assertEqual(mtime_1, mtime_2)

    def test_invalid_size_spec_falls_back_to_original_url(self):
        self.track.cover = _make_image_file()
        self.track.save()
        self.assertEqual(thumbnail_url(self.track.cover, "not-a-size"), self.track.cover.url)
