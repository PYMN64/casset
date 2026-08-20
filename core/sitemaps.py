"""Sitemaps for Casset.

Only genuinely public, indexable URLs belong here. A sitemap that lists
pages a crawler cannot reach (drafts, private playlists, staff consoles)
does not just waste crawl budget — it teaches Google that our URLs 404 or
redirect, which costs us on the pages that *do* matter.

Every queryset below therefore mirrors exactly the visibility check the
corresponding view applies.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """The handful of evergreen entry points."""

    priority = 0.8
    changefreq = "daily"
    protocol = "https"

    def items(self):
        return ["discover", "trending", "track_list", "terms", "privacy"]

    def location(self, item):
        return reverse(item)

    def priority_for(self, item):  # pragma: no cover - documentation hook
        return 1.0 if item == "discover" else 0.6


class TrackSitemap(Sitemap):
    """Approved, public tracks only — the same filter track_detail enforces."""

    changefreq = "weekly"
    priority = 0.7
    limit = 2000
    protocol = "https"

    def items(self):
        from tracks.models import Track

        return (
            Track.objects.filter(
                status=Track.Status.APPROVED,
                visibility=Track.Visibility.PUBLIC,
            )
            .only("slug", "updated_at", "created_at")
            .order_by("-created_at")
        )

    def location(self, obj):
        return reverse("track_detail", kwargs={"slug": obj.slug})

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or obj.created_at


class ShowSitemap(Sitemap):
    """Public albums/shows.

    `show_detail` is the only public album page — `album_edit` is
    creator-only, so it must never appear here.
    """

    changefreq = "weekly"
    priority = 0.6
    limit = 2000
    protocol = "https"

    def items(self):
        from tracks.models import Album

        return Album.objects.filter(is_public=True).order_by("-created_at")

    def location(self, obj):
        return reverse("show_detail", kwargs={"album_id": obj.id})

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or obj.created_at


class CreatorSitemap(Sitemap):
    """Profiles that have a public handle.

    Handle-less accounts are excluded deliberately: /@u-a1b2c3d4e5/ is an
    internal identifier, not a page anyone should land on from search.
    """

    changefreq = "weekly"
    priority = 0.7
    limit = 2000
    protocol = "https"

    def items(self):
        from accounts.models import UserProfile

        return (
            UserProfile.objects.filter(
                public_handle__isnull=False,
                user__is_active=True,
            )
            .exclude(public_handle="")
            .order_by("-updated_at")
        )

    def location(self, obj):
        return reverse("public_profile_by_handle", kwargs={"handle": obj.public_handle})

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "static": StaticViewSitemap,
    "tracks": TrackSitemap,
    "shows": ShowSitemap,
    "creators": CreatorSitemap,
}
