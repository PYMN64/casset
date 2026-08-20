from django.test import TestCase
from django.urls import reverse

from core.test_utils import make_superuser, make_user
from notifications.models import Notification
from tracks.models import Track

from .models import (
    Comment,
    CommentLike,
    CreatorBlock,
    CreatorFollow,
    Repost,
    TrackFavorite,
    TrackLike,
)


def make_public_track(creator, **extra):
    defaults = dict(
        title="T",
        status=Track.Status.APPROVED,
        visibility=Track.Visibility.PUBLIC,
    )
    defaults.update(extra)
    return Track.objects.create(creator=creator, **defaults)


class ToggleLikeViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("like_creator")
        self.liker = make_user("like_liker")
        self.track = make_public_track(self.creator, slug="like-t")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_like"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 401)

    def test_invalid_track_id(self):
        self.client.login(username="like_liker", password="pass12345")
        resp = self.client.post(reverse("api_like"), {"track_id": "abc"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_track_404s(self):
        self.client.login(username="like_liker", password="pass12345")
        resp = self.client.post(reverse("api_like"), {"track_id": 999999})
        self.assertEqual(resp.status_code, 404)

    def test_toggle_on_then_off_updates_like_count(self):
        self.client.login(username="like_liker", password="pass12345")
        r1 = self.client.post(reverse("api_like"), {"track_id": self.track.id})
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()
        self.assertTrue(data1["liked"])
        self.assertEqual(data1["like_count"], 1)

        r2 = self.client.post(reverse("api_like"), {"track_id": self.track.id})
        data2 = r2.json()
        self.assertFalse(data2["liked"])
        self.assertEqual(data2["like_count"], 0)
        self.assertEqual(TrackLike.objects.count(), 0)

    def test_like_notifies_creator(self):
        self.client.login(username="like_liker", password="pass12345")
        self.client.post(reverse("api_like"), {"track_id": self.track.id})
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator, verb="track_liked", track=self.track
            ).exists()
        )

    def test_creator_liking_own_track_does_not_self_notify(self):
        self.client.login(username="like_creator", password="pass12345")
        self.client.post(reverse("api_like"), {"track_id": self.track.id})
        self.assertFalse(
            Notification.objects.filter(recipient=self.creator, verb="track_liked").exists()
        )


class ToggleFollowViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("fol_creator")
        self.follower = make_user("fol_follower")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_follow"), {"creator_username": self.creator.username})
        self.assertEqual(resp.status_code, 401)

    def test_unknown_creator_404s(self):
        self.client.login(username="fol_follower", password="pass12345")
        resp = self.client.post(reverse("api_follow"), {"creator_username": "doesnotexist"})
        self.assertEqual(resp.status_code, 404)

    def test_cannot_follow_self(self):
        self.client.login(username="fol_creator", password="pass12345")
        resp = self.client.post(reverse("api_follow"), {"creator_username": self.creator.username})
        self.assertEqual(resp.status_code, 400)

    def test_toggle_on_then_off_updates_follower_count(self):
        self.client.login(username="fol_follower", password="pass12345")
        r1 = self.client.post(reverse("api_follow"), {"creator_username": self.creator.username})
        data1 = r1.json()
        self.assertTrue(data1["following"])
        self.assertEqual(data1["follower_count"], 1)

        r2 = self.client.post(reverse("api_follow"), {"creator_username": self.creator.username})
        data2 = r2.json()
        self.assertFalse(data2["following"])
        self.assertEqual(data2["follower_count"], 0)
        self.assertEqual(CreatorFollow.objects.count(), 0)

    def test_follow_notifies_creator(self):
        self.client.login(username="fol_follower", password="pass12345")
        self.client.post(reverse("api_follow"), {"creator_username": self.creator.username})
        self.assertTrue(
            Notification.objects.filter(recipient=self.creator, verb="new_follower").exists()
        )


class CommentAddViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("cmt_creator")
        self.commenter = make_user("cmt_commenter")
        self.track = make_public_track(self.creator, slug="cmt-t")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_comment_add"), {"track_id": self.track.id, "body": "hi"})
        self.assertEqual(resp.status_code, 401)

    def test_invalid_track_id(self):
        self.client.login(username="cmt_commenter", password="pass12345")
        resp = self.client.post(reverse("api_comment_add"), {"track_id": "x", "body": "hi"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_track_404s(self):
        self.client.login(username="cmt_commenter", password="pass12345")
        resp = self.client.post(reverse("api_comment_add"), {"track_id": 999999, "body": "hi"})
        self.assertEqual(resp.status_code, 404)

    def test_private_track_not_owner_404s(self):
        private = Track.objects.create(
            creator=self.creator, title="P", slug="cmt-priv",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PRIVATE,
        )
        self.client.login(username="cmt_commenter", password="pass12345")
        resp = self.client.post(reverse("api_comment_add"), {"track_id": private.id, "body": "hi"})
        self.assertEqual(resp.status_code, 404)

    def test_empty_body_rejected(self):
        self.client.login(username="cmt_commenter", password="pass12345")
        resp = self.client.post(reverse("api_comment_add"), {"track_id": self.track.id, "body": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["reason"], "empty_body")

    def test_too_long_body_rejected(self):
        self.client.login(username="cmt_commenter", password="pass12345")
        resp = self.client.post(
            reverse("api_comment_add"), {"track_id": self.track.id, "body": "x" * 1501}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["reason"], "too_long")

    def test_comments_disabled_rejected(self):
        self.track.allow_comments = False
        self.track.save(update_fields=["allow_comments"])
        self.client.login(username="cmt_commenter", password="pass12345")
        resp = self.client.post(reverse("api_comment_add"), {"track_id": self.track.id, "body": "hi"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["reason"], "comments_disabled")

    def test_valid_comment_creates_record_and_notifies_creator(self):
        self.client.login(username="cmt_commenter", password="pass12345")
        resp = self.client.post(reverse("api_comment_add"), {"track_id": self.track.id, "body": "nice track"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["comment"]["body"], "nice track")

        comment = Comment.objects.get(track=self.track)
        self.assertEqual(comment.author, self.commenter)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator, verb="track_comment", comment=comment
            ).exists()
        )

    def test_owner_commenting_on_own_track_does_not_self_notify(self):
        self.client.login(username="cmt_creator", password="pass12345")
        self.client.post(reverse("api_comment_add"), {"track_id": self.track.id, "body": "self note"})
        self.assertFalse(
            Notification.objects.filter(recipient=self.creator, verb="track_comment").exists()
        )


class CommentDeleteViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("del_creator")
        self.author = make_user("del_author")
        self.other = make_user("del_other")
        self.staff = make_superuser("del_staff")
        self.track = make_public_track(self.creator, slug="del-t")
        self.comment = Comment.objects.create(track=self.track, author=self.author, body="x")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_comment_delete", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 401)

    def test_non_author_non_staff_forbidden(self):
        self.client.login(username="del_other", password="pass12345")
        resp = self.client.post(reverse("api_comment_delete", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())

    def test_author_can_delete(self):
        self.client.login(username="del_author", password="pass12345")
        resp = self.client.post(reverse("api_comment_delete", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_staff_can_delete(self):
        self.client.login(username="del_staff", password="pass12345")
        resp = self.client.post(reverse("api_comment_delete", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())


class CommentLikeViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("cl_creator")
        self.author = make_user("cl_author")
        self.liker = make_user("cl_liker")
        self.track = make_public_track(self.creator, slug="cl-t")
        self.comment = Comment.objects.create(track=self.track, author=self.author, body="x")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_comment_like", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 401)

    def test_hidden_comment_404s(self):
        self.comment.is_public = False
        self.comment.save(update_fields=["is_public"])
        self.client.login(username="cl_liker", password="pass12345")
        resp = self.client.post(reverse("api_comment_like", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 404)

    def test_toggle_on_then_off(self):
        self.client.login(username="cl_liker", password="pass12345")
        r1 = self.client.post(reverse("api_comment_like", args=[self.comment.id]))
        data1 = r1.json()
        self.assertTrue(data1["liked"])
        self.assertEqual(data1["like_count"], 1)

        r2 = self.client.post(reverse("api_comment_like", args=[self.comment.id]))
        data2 = r2.json()
        self.assertFalse(data2["liked"])
        self.assertEqual(data2["like_count"], 0)
        self.assertEqual(CommentLike.objects.count(), 0)

    def test_comment_like_notifies_author(self):
        self.client.login(username="cl_liker", password="pass12345")
        self.client.post(reverse("api_comment_like", args=[self.comment.id]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.author, verb="comment_liked", comment=self.comment
            ).exists()
        )

    def test_comment_on_now_private_track_not_owner_404s(self):
        """Regression: liking must respect the track's current visibility,
        not just the comment's own is_public flag — a track can go private
        after comments already exist on it."""
        self.track.visibility = Track.Visibility.PRIVATE
        self.track.save(update_fields=["visibility"])
        self.client.login(username="cl_liker", password="pass12345")
        resp = self.client.post(reverse("api_comment_like", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 404)

    def test_track_owner_can_still_like_comment_on_own_private_track(self):
        self.track.visibility = Track.Visibility.PRIVATE
        self.track.save(update_fields=["visibility"])
        self.client.login(username="cl_creator", password="pass12345")
        resp = self.client.post(reverse("api_comment_like", args=[self.comment.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["liked"])


class ToggleFavoriteViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("fav_creator")
        self.user = make_user("fav_user")
        self.track = make_public_track(self.creator, slug="fav-t")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_favorite"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 401)

    def test_invalid_track_id(self):
        self.client.login(username="fav_user", password="pass12345")
        resp = self.client.post(reverse("api_favorite"), {"track_id": "abc"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_track_404s(self):
        self.client.login(username="fav_user", password="pass12345")
        resp = self.client.post(reverse("api_favorite"), {"track_id": 999999})
        self.assertEqual(resp.status_code, 404)

    def test_private_track_not_owner_404s(self):
        private = Track.objects.create(
            creator=self.creator, title="P", slug="fav-priv",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PRIVATE,
        )
        self.client.login(username="fav_user", password="pass12345")
        resp = self.client.post(reverse("api_favorite"), {"track_id": private.id})
        self.assertEqual(resp.status_code, 404)

    def test_toggle_on_then_off(self):
        self.client.login(username="fav_user", password="pass12345")
        r1 = self.client.post(reverse("api_favorite"), {"track_id": self.track.id})
        data1 = r1.json()
        self.assertTrue(data1["favorited"])
        self.assertEqual(data1["favorite_count"], 1)

        r2 = self.client.post(reverse("api_favorite"), {"track_id": self.track.id})
        data2 = r2.json()
        self.assertFalse(data2["favorited"])
        self.assertEqual(data2["favorite_count"], 0)
        self.assertEqual(TrackFavorite.objects.count(), 0)

    def test_owner_can_favorite_own_track(self):
        self.client.login(username="fav_creator", password="pass12345")
        resp = self.client.post(reverse("api_favorite"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["favorited"])


class ToggleRepostViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("repost_creator")
        self.user = make_user("repost_user")
        self.track = make_public_track(self.creator, slug="repost-t")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_repost"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 401)

    def test_invalid_track_id(self):
        self.client.login(username="repost_user", password="pass12345")
        resp = self.client.post(reverse("api_repost"), {"track_id": "abc"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_track_404s(self):
        self.client.login(username="repost_user", password="pass12345")
        resp = self.client.post(reverse("api_repost"), {"track_id": 999999})
        self.assertEqual(resp.status_code, 404)

    def test_private_track_not_owner_404s(self):
        private = Track.objects.create(
            creator=self.creator, title="P", slug="repost-priv",
            status=Track.Status.APPROVED, visibility=Track.Visibility.PRIVATE,
        )
        self.client.login(username="repost_user", password="pass12345")
        resp = self.client.post(reverse("api_repost"), {"track_id": private.id})
        self.assertEqual(resp.status_code, 404)

    def test_toggle_on_then_off(self):
        self.client.login(username="repost_user", password="pass12345")
        r1 = self.client.post(reverse("api_repost"), {"track_id": self.track.id})
        data1 = r1.json()
        self.assertTrue(data1["reposted"])
        self.assertEqual(data1["repost_count"], 1)

        r2 = self.client.post(reverse("api_repost"), {"track_id": self.track.id})
        data2 = r2.json()
        self.assertFalse(data2["reposted"])
        self.assertEqual(data2["repost_count"], 0)
        self.assertEqual(Repost.objects.count(), 0)

    def test_cannot_repost_own_track(self):
        self.client.login(username="repost_creator", password="pass12345")
        resp = self.client.post(reverse("api_repost"), {"track_id": self.track.id})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["reason"], "cannot_repost_own_track")

    def test_repost_notifies_creator(self):
        self.client.login(username="repost_user", password="pass12345")
        self.client.post(reverse("api_repost"), {"track_id": self.track.id})
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.creator, verb="track_reposted", track=self.track
            ).exists()
        )


class ToggleBlockViewTests(TestCase):
    def setUp(self):
        self.creator = make_user("blk_creator")
        self.pest = make_user("blk_pest")

    def test_requires_login(self):
        resp = self.client.post(reverse("api_block"), {"blocked_username": self.pest.username})
        self.assertEqual(resp.status_code, 401)

    def test_unknown_user_404s(self):
        self.client.login(username="blk_creator", password="pass12345")
        resp = self.client.post(reverse("api_block"), {"blocked_username": "doesnotexist"})
        self.assertEqual(resp.status_code, 404)

    def test_cannot_block_self(self):
        self.client.login(username="blk_creator", password="pass12345")
        resp = self.client.post(reverse("api_block"), {"blocked_username": self.creator.username})
        self.assertEqual(resp.status_code, 400)

    def test_toggle_on_then_off(self):
        self.client.login(username="blk_creator", password="pass12345")
        r1 = self.client.post(reverse("api_block"), {"blocked_username": self.pest.username})
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["blocked"])
        self.assertTrue(
            CreatorBlock.objects.filter(creator=self.creator, blocked_user=self.pest).exists()
        )

        r2 = self.client.post(reverse("api_block"), {"blocked_username": self.pest.username})
        self.assertFalse(r2.json()["blocked"])
        self.assertEqual(CreatorBlock.objects.count(), 0)


class BlockedCommenterTests(TestCase):
    """A creator blocking a user must stop that user from commenting on the
    creator's tracks (Phase 3) — the block is creator-scoped, not global."""

    def setUp(self):
        self.creator = make_user("bc_creator")
        self.pest = make_user("bc_pest")
        self.other_creator = make_user("bc_other_creator")
        self.track = make_public_track(self.creator, slug="bc-t")
        self.other_track = make_public_track(self.other_creator, slug="bc-other-t")
        CreatorBlock.objects.create(creator=self.creator, blocked_user=self.pest)

    def test_blocked_user_cannot_comment_on_blockers_track(self):
        self.client.login(username="bc_pest", password="pass12345")
        resp = self.client.post(
            reverse("api_comment_add"), {"track_id": self.track.id, "body": "spam"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["reason"], "blocked")
        self.assertEqual(Comment.objects.count(), 0)

    def test_blocked_user_can_still_comment_on_other_creators_track(self):
        self.client.login(username="bc_pest", password="pass12345")
        resp = self.client.post(
            reverse("api_comment_add"), {"track_id": self.other_track.id, "body": "hi"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
