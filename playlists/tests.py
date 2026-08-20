"""playlists/tests.py — was an empty stub before this session despite the
whole app (library page, playlist CRUD, the add-to-playlist modal) having
zero coverage. Two real bugs were found and fixed while writing these:

1. library_view's `playlists` queryset never annotated `item_count`, so
   {{ p.item_count }} in library.html silently rendered empty for every
   playlist — only api_playlist_mine (used by the JS modal) had it.
2. playlist_detail.html referenced `{{ playlist.name }}` but the view's
   context key is `pl` — the playlist name never rendered on its own page.
"""

from django.test import TestCase
from django.urls import reverse

from core.test_utils import make_user
from tracks.models import Track

from .models import Playlist, PlaylistItem


def make_public_track(creator, **extra):
    defaults = dict(title="T", status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC)
    defaults.update(extra)
    return Track.objects.create(creator=creator, **defaults)


class LibraryViewTests(TestCase):
    def setUp(self):
        self.user = make_user("lib_user")
        self.client.login(username="lib_user", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("library"))
        self.assertEqual(resp.status_code, 302)

    def test_item_count_annotation_present(self):
        """Regression: library_view used to omit this annotation, so the
        page always showed '0 tracks' for every playlist regardless of
        actual contents."""
        pl = Playlist.objects.create(owner=self.user, name="Road trip")
        track = make_public_track(make_user("lib_creator"))
        PlaylistItem.objects.create(playlist=pl, track=track)

        resp = self.client.get(reverse("library"))
        found = [p for p in resp.context["playlists"] if p.id == pl.id][0]
        self.assertEqual(found.item_count, 1)
        self.assertContains(resp, "1 ترک")

    def test_only_shows_own_playlists(self):
        other = make_user("lib_other")
        Playlist.objects.create(owner=other, name="Not mine")
        resp = self.client.get(reverse("library"))
        names = [p.name for p in resp.context["playlists"]]
        self.assertNotIn("Not mine", names)


class PlaylistDetailViewTests(TestCase):
    def setUp(self):
        self.user = make_user("pld_user")
        self.pl = Playlist.objects.create(owner=self.user, name="My Mix")
        self.client.login(username="pld_user", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 302)

    def test_other_users_playlist_404s(self):
        make_user("pld_stranger")
        self.client.login(username="pld_stranger", password="pass12345")
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 404)

    def test_playlist_name_renders(self):
        """Regression: the template used to reference the undefined
        `playlist` context var instead of `pl` — the name never showed."""
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertContains(resp, "My Mix")
        self.assertContains(resp, "<h1>My Mix</h1>", html=False)

    def test_items_render_with_track_titles(self):
        creator = make_user("pld_creator")
        track = make_public_track(creator, title="Great Song")
        PlaylistItem.objects.create(playlist=self.pl, track=track)
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertContains(resp, "Great Song")


class PlaylistCreateDeleteApiTests(TestCase):
    def setUp(self):
        self.user = make_user("pl_api_user")
        self.client.login(username="pl_api_user", password="pass12345")

    def test_create_requires_name(self):
        resp = self.client.post(reverse("api_playlist_create"), {"name": ""})
        self.assertEqual(resp.status_code, 400)

    def test_create_and_delete_round_trip(self):
        resp = self.client.post(reverse("api_playlist_create"), {"name": "New list"})
        self.assertEqual(resp.status_code, 200)
        pl_id = resp.json()["playlist_id"]
        self.assertTrue(Playlist.objects.filter(id=pl_id, owner=self.user).exists())

        resp2 = self.client.post(reverse("api_playlist_delete"), {"playlist_id": pl_id})
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(Playlist.objects.filter(id=pl_id).exists())

    def test_cannot_delete_others_playlist(self):
        other = make_user("pl_api_other")
        pl = Playlist.objects.create(owner=other, name="Theirs")
        resp = self.client.post(reverse("api_playlist_delete"), {"playlist_id": pl.id})
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Playlist.objects.filter(id=pl.id).exists())


class PlaylistToggleTrackApiTests(TestCase):
    def setUp(self):
        self.user = make_user("pl_toggle_user")
        self.pl = Playlist.objects.create(owner=self.user, name="Mix")
        self.creator = make_user("pl_toggle_creator")
        self.track = make_public_track(self.creator)
        self.client.login(username="pl_toggle_user", password="pass12345")

    def test_toggle_adds_then_removes(self):
        r1 = self.client.post(
            reverse("api_playlist_toggle_track"), {"playlist_id": self.pl.id, "track_id": self.track.id}
        )
        self.assertTrue(r1.json()["added"])
        self.assertEqual(r1.json()["count"], 1)

        r2 = self.client.post(
            reverse("api_playlist_toggle_track"), {"playlist_id": self.pl.id, "track_id": self.track.id}
        )
        self.assertFalse(r2.json()["added"])
        self.assertEqual(r2.json()["count"], 0)

    def test_private_unapproved_track_not_addable(self):
        draft = Track.objects.create(creator=self.creator, title="Draft", status=Track.Status.DRAFT)
        resp = self.client.post(
            reverse("api_playlist_toggle_track"), {"playlist_id": self.pl.id, "track_id": draft.id}
        )
        self.assertEqual(resp.status_code, 404)

    def test_api_mine_reports_item_count(self):
        PlaylistItem.objects.create(playlist=self.pl, track=self.track)
        resp = self.client.get(reverse("api_playlist_mine"))
        data = resp.json()["playlists"]
        self.assertEqual(data[0]["item_count"], 1)
