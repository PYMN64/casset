"""playlists/tests.py — was an empty stub before this session despite the
whole app (library page, playlist CRUD, the add-to-playlist modal) having
zero coverage. Two real bugs were found and fixed while writing these:

1. library_view's `playlists` queryset never annotated `item_count`, so
   {{ p.item_count }} in library.html silently rendered empty for every
   playlist — only api_playlist_mine (used by the JS modal) had it.
2. playlist_detail.html referenced `{{ playlist.name }}` but the view's
   context key is `pl` — the playlist name never rendered on its own page.
"""

import json

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
        # The count must actually reach the page, not just the context.
        self.assertContains(resp, "1 اثر")

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

    def test_anonymous_access_to_private_playlist_404s(self):
        """A private playlist (the default) is not visible to a logged-out
        visitor, exactly like a private track — a plain 404, not a
        login-redirect, since the resource simply isn't there for them."""
        self.client.logout()
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 404)

    def test_anonymous_access_to_public_playlist_succeeds(self):
        self.pl.is_private = False
        self.pl.save(update_fields=["is_private"])
        self.client.logout()
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["is_owner"])

    def test_other_users_private_playlist_404s(self):
        make_user("pld_stranger")
        self.client.login(username="pld_stranger", password="pass12345")
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 404)

    def test_other_users_public_playlist_is_viewable_but_not_editable(self):
        self.pl.is_private = False
        self.pl.save(update_fields=["is_private"])
        make_user("pld_stranger")
        self.client.login(username="pld_stranger", password="pass12345")
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["is_owner"])
        # A non-owner gets a static heading, never the rename input or the
        # per-row remove buttons.
        self.assertContains(resp, "My Mix")
        self.assertNotContains(resp, "data-pl-rename-form")
        self.assertNotContains(resp, "data-pl-remove")

    def test_playlist_name_renders(self):
        """Regression: the template used to reference the undefined
        `playlist` context var instead of `pl` — the name never showed.
        The owner's view is now an editable rename input, not a static
        <h1> (see test_other_users_public_playlist_is_viewable_but_not_editable
        for the non-owner <h1> case)."""
        resp = self.client.get(reverse("playlist_detail", args=[self.pl.id]))
        self.assertContains(resp, "My Mix")
        self.assertContains(resp, 'value="My Mix"', html=False)

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


class ApiPlaylistRenameTests(TestCase):
    def setUp(self):
        self.user = make_user("rename_owner")
        self.other = make_user("rename_other")
        self.pl = Playlist.objects.create(owner=self.user, name="Old Name")
        self.client.login(username="rename_owner", password="pass12345")

    def test_rename_updates_name(self):
        resp = self.client.post(reverse("api_playlist_rename"), {"playlist_id": self.pl.id, "name": "New Name"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.name, "New Name")

    def test_empty_name_rejected(self):
        resp = self.client.post(reverse("api_playlist_rename"), {"playlist_id": self.pl.id, "name": "  "})
        self.assertEqual(resp.status_code, 400)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.name, "Old Name")

    def test_non_owner_cannot_rename(self):
        self.client.logout()
        self.client.login(username="rename_other", password="pass12345")
        resp = self.client.post(reverse("api_playlist_rename"), {"playlist_id": self.pl.id, "name": "Hijacked"})
        self.assertEqual(resp.status_code, 404)
        self.pl.refresh_from_db()
        self.assertEqual(self.pl.name, "Old Name")


class ApiPlaylistReorderTests(TestCase):
    def setUp(self):
        self.user = make_user("reorder_owner")
        self.creator = make_user("reorder_creator")
        self.pl = Playlist.objects.create(owner=self.user, name="Mix")
        self.t1 = make_public_track(self.creator, title="One")
        self.t2 = make_public_track(self.creator, title="Two")
        self.t3 = make_public_track(self.creator, title="Three")
        self.i1 = PlaylistItem.objects.create(playlist=self.pl, track=self.t1, order=1)
        self.i2 = PlaylistItem.objects.create(playlist=self.pl, track=self.t2, order=2)
        self.i3 = PlaylistItem.objects.create(playlist=self.pl, track=self.t3, order=3)
        self.client.login(username="reorder_owner", password="pass12345")

    def _order(self):
        return list(
            PlaylistItem.objects.filter(playlist=self.pl).order_by("order", "-created_at").values_list("id", flat=True)
        )

    def test_move_up_swaps_with_previous(self):
        resp = self.client.post(
            reverse("api_playlist_reorder"),
            {"playlist_id": self.pl.id, "item_id": self.i2.id, "direction": "up"},
        )
        self.assertTrue(resp.json()["moved"])
        self.assertEqual(self._order(), [self.i2.id, self.i1.id, self.i3.id])

    def test_move_down_swaps_with_next(self):
        resp = self.client.post(
            reverse("api_playlist_reorder"),
            {"playlist_id": self.pl.id, "item_id": self.i1.id, "direction": "down"},
        )
        self.assertTrue(resp.json()["moved"])
        self.assertEqual(self._order(), [self.i2.id, self.i1.id, self.i3.id])

    def test_move_first_item_up_is_a_noop(self):
        resp = self.client.post(
            reverse("api_playlist_reorder"),
            {"playlist_id": self.pl.id, "item_id": self.i1.id, "direction": "up"},
        )
        self.assertTrue(resp.json()["ok"])
        self.assertFalse(resp.json()["moved"])
        self.assertEqual(self._order(), [self.i1.id, self.i2.id, self.i3.id])

    def test_non_owner_cannot_reorder(self):
        make_user("reorder_stranger")
        self.client.logout()
        self.client.login(username="reorder_stranger", password="pass12345")
        resp = self.client.post(
            reverse("api_playlist_reorder"),
            {"playlist_id": self.pl.id, "item_id": self.i1.id, "direction": "down"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._order(), [self.i1.id, self.i2.id, self.i3.id])


class PlaylistDragReorderTests(TestCase):
    """Drag-to-reorder posts the whole order as JSON; the arrow buttons
    post a single step. Both must land on the same re-sequenced result,
    and neither may touch rows the caller does not own."""

    def setUp(self):
        self.user = make_user("drag_owner")
        self.other = make_user("drag_other")
        self.client.login(username="drag_owner", password="pass12345")
        self.pl = Playlist.objects.create(owner=self.user, name="Mix")
        creator = make_user("drag_creator")
        self.items = [
            PlaylistItem.objects.create(
                playlist=self.pl,
                track=make_public_track(creator, title=f"Song {i}"),
                order=i,
            )
            for i in range(1, 4)
        ]

    def _order(self):
        return list(
            PlaylistItem.objects.filter(playlist=self.pl)
            .order_by("order")
            .values_list("id", flat=True)
        )

    def test_full_order_is_applied(self):
        reversed_ids = list(reversed([i.id for i in self.items]))
        resp = self.client.post(
            reverse("api_playlist_reorder"),
            data=json.dumps({"order": reversed_ids}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(self._order(), reversed_ids)

    def test_orders_are_resequenced_from_one(self):
        """Ties in `order` are what made the old data sort unpredictably;
        every write must leave a clean 1..N sequence."""
        ids = [i.id for i in self.items]
        self.client.post(
            reverse("api_playlist_reorder"),
            data=json.dumps({"order": list(reversed(ids))}),
            content_type="application/json",
        )
        orders = sorted(
            PlaylistItem.objects.filter(playlist=self.pl).values_list("order", flat=True)
        )
        self.assertEqual(orders, [1, 2, 3])

    def test_cannot_reorder_someone_elses_playlist(self):
        theirs = Playlist.objects.create(owner=self.other, name="Theirs")
        creator = make_user("drag_creator2")
        item = PlaylistItem.objects.create(
            playlist=theirs, track=make_public_track(creator, title="Not Yours"), order=1
        )
        resp = self.client.post(
            reverse("api_playlist_reorder"),
            data=json.dumps({"order": [item.id]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.order, 1)

    def test_mixing_in_a_foreign_id_is_rejected_wholesale(self):
        """A partially-valid list must not be partially applied."""
        theirs = Playlist.objects.create(owner=self.other, name="Theirs")
        creator = make_user("drag_creator3")
        foreign = PlaylistItem.objects.create(
            playlist=theirs, track=make_public_track(creator, title="Foreign"), order=1
        )
        before = self._order()
        resp = self.client.post(
            reverse("api_playlist_reorder"),
            data=json.dumps({"order": [self.items[0].id, foreign.id]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._order(), before)

    def test_malformed_body_is_rejected(self):
        for body in ("not json", json.dumps({"order": "nope"}), json.dumps({})):
            with self.subTest(body=body):
                resp = self.client.post(
                    reverse("api_playlist_reorder"),
                    data=body,
                    content_type="application/json",
                )
                self.assertEqual(resp.status_code, 400)

    def test_arrow_buttons_still_work(self):
        """The single-step path is what touch and keyboard users get; it
        must keep working alongside drag-and-drop."""
        ids = [i.id for i in self.items]
        resp = self.client.post(reverse("api_playlist_reorder"), {
            "playlist_id": self.pl.id, "item_id": ids[2], "direction": "up",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._order(), [ids[0], ids[2], ids[1]])
