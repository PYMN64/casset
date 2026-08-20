"""Podcast RSS feed — the single most load-bearing "Phase 2" feature.

Without this, a podcast published on Casset can never appear on Apple
Podcasts, Google Podcasts, or any other podcast app — they all discover and
update shows exclusively via RSS with the itunes: namespace extensions
below. This is not a UI nice-to-have; it's what makes "publish a podcast"
actually mean something outside Casset itself.

Reuses tracks.Album as the "Show" — Album already has content_type=PODCAST,
title, description, cover, and a creator, and Track already has an `album`
FK. No new model needed (Constitution, CLAUDE.md §2: no rewrite, build on
what exists).
"""

from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed

from .models import Album, Track


class ITunesFeedGenerator(Rss201rev2Feed):
    """Adds the itunes: namespace tags podcast directories require."""

    def rss_attributes(self):
        attrs = super().rss_attributes()
        attrs["xmlns:itunes"] = "http://www.itunes.com/dtds/podcast-1.0.dtd"
        return attrs

    def add_root_elements(self, handler):
        super().add_root_elements(handler)
        handler.addQuickElement("itunes:author", self.feed.get("author_name") or "")
        handler.addQuickElement(
            "itunes:explicit", "true" if self.feed.get("itunes_explicit") else "false"
        )
        if self.feed.get("itunes_image"):
            handler.addQuickElement("itunes:image", None, {"href": self.feed["itunes_image"]})
        handler.addQuickElement(
            "itunes:category", "", {"text": self.feed.get("itunes_category") or "Music"}
        )
        handler.addQuickElement("itunes:type", "episodic")

    def add_item_elements(self, handler, item):
        super().add_item_elements(handler, item)
        if item.get("itunes_duration"):
            handler.addQuickElement("itunes:duration", item["itunes_duration"])
        handler.addQuickElement(
            "itunes:explicit", "true" if item.get("itunes_explicit") else "false"
        )


class ShowRSSFeed(Feed):
    feed_type = ITunesFeedGenerator

    def __call__(self, request, *args, **kwargs):
        # Feed's item_* hooks don't receive `request`, but building an
        # absolute enclosure URL (required by every podcast app) does.
        self.request = request
        return super().__call__(request, *args, **kwargs)

    def get_object(self, request, album_id):
        return get_object_or_404(
            Album, id=album_id, content_type=Album.ContentType.PODCAST, is_public=True,
        )

    def title(self, obj):
        return obj.title

    def link(self, obj):
        return reverse("show_detail", args=[obj.id])

    def description(self, obj):
        return obj.description or obj.title

    def author_name(self, obj):
        return obj.creator.profile.public_name()

    def feed_extra_kwargs(self, obj):
        return {
            "itunes_image": self.request.build_absolute_uri(obj.cover.url) if obj.cover else None,
            "itunes_explicit": False,
            "itunes_category": "Society & Culture",
        }

    def items(self, obj):
        return (
            Track.objects.filter(
                album=obj, status=Track.Status.APPROVED, visibility=Track.Visibility.PUBLIC,
            )
            .exclude(audio="")
            .order_by("-published_at")
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.description or item.title

    def item_link(self, item):
        return reverse("track_detail", args=[item.slug])

    def item_pubdate(self, item):
        return item.published_at or item.created_at

    def item_guid(self, item):
        return self.request.build_absolute_uri(reverse("track_detail", args=[item.slug]))

    def item_enclosure_url(self, item):
        return self.request.build_absolute_uri(item.audio.url)

    def item_enclosure_length(self, item):
        try:
            return item.audio.size
        except (OSError, ValueError):
            return 0

    def item_enclosure_mime_type(self, item):
        return "audio/mpeg"

    def item_extra_kwargs(self, item):
        minutes, seconds = divmod(item.duration_seconds or 0, 60)
        return {
            "itunes_duration": f"{minutes}:{seconds:02d}",
            "itunes_explicit": item.explicit,
        }
