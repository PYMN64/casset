"""schema.org JSON-LD builders.

Rich results are the difference between a Casset track appearing in Google
as a bare blue link and appearing with artwork, artist and duration. The
schema type has to match the content: a podcast episode marked up as a
MusicRecording is worse than no markup, because Google will distrust the
rest of the page's markup too.

Everything here returns a JSON string ready to drop inside a
<script type="application/ld+json"> block. `json.dumps` handles the
escaping, so the template can use |safe without opening an injection path
for user-supplied titles and descriptions.
"""

from __future__ import annotations

import json


def _absolute(request, url: str) -> str:
    """Absolute URL, whether *url* is already absolute (S3) or path-only."""
    if not url:
        return ""
    return request.build_absolute_uri(url)


def _iso_duration(seconds: int) -> str:
    """ISO 8601 duration, which is the only format schema.org accepts."""
    seconds = int(seconds or 0)
    if seconds <= 0:
        return ""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    out = "PT"
    if hours:
        out += f"{hours}H"
    if minutes:
        out += f"{minutes}M"
    if secs or out == "PT":
        out += f"{secs}S"
    return out


def _person(request, user) -> dict:
    profile = getattr(user, "profile", None)
    data = {
        "@type": "Person",
        "name": profile.public_name() if profile else user.username,
    }
    if profile:
        data["url"] = request.build_absolute_uri(profile.profile_url)
    return data


def build_track_jsonld(request, track) -> str:
    """MusicRecording, PodcastEpisode, AudioBook or VideoObject."""
    from tracks.models import Track

    type_map = {
        Track.ContentType.MUSIC: "MusicRecording",
        Track.ContentType.PODCAST: "PodcastEpisode",
        Track.ContentType.AUDIOBOOK: "AudioBook",
        Track.ContentType.VIDEO: "VideoObject",
    }
    schema_type = type_map.get(track.content_type, "AudioObject")

    data = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": track.title,
        "url": request.build_absolute_uri(),
        "datePublished": (track.published_at or track.created_at).date().isoformat(),
        "inLanguage": track.language or "fa",
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/ListenAction",
            "userInteractionCount": track.play_count,
        },
    }

    if track.description:
        data["description"] = track.description[:500]
    if track.cover:
        data["image"] = _absolute(request, track.cover.url)
    duration = _iso_duration(track.duration_seconds)
    if duration:
        data["duration"] = duration

    creator = _person(request, track.creator)
    if schema_type == "MusicRecording":
        data["byArtist"] = creator
        if track.album:
            data["inAlbum"] = {"@type": "MusicAlbum", "name": track.album.title}
    elif schema_type == "PodcastEpisode":
        data["author"] = creator
        if track.album:
            data["partOfSeries"] = {
                "@type": "PodcastSeries",
                "name": track.album.title,
                "url": request.build_absolute_uri(f"/show/{track.album_id}/"),
            }
    elif schema_type == "AudioBook":
        data["author"] = creator
        data["readBy"] = creator
    else:
        data["uploadDate"] = data["datePublished"]
        data["creator"] = creator

    # A media URL is only advertised when the file is genuinely public.
    # Handing Google a contentUrl for a private or unapproved track would
    # publish exactly what the visibility setting says not to.
    if track.audio and track.visibility == Track.Visibility.PUBLIC and track.status == Track.Status.APPROVED:
        data["contentUrl"] = _absolute(request, track.audio.url)

    return json.dumps(data, ensure_ascii=False)


def build_profile_jsonld(request, user_obj, profile, stats) -> str:
    """ProfilePage wrapping a Person — the pairing Google expects for a
    creator page, rather than a bare Person floating on a URL."""
    person = {
        "@type": "Person",
        "name": profile.public_name(),
        "url": request.build_absolute_uri(profile.profile_url),
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/FollowAction",
            "userInteractionCount": stats.get("followers", 0),
        },
    }
    if profile.bio:
        person["description"] = profile.bio[:500]
    if profile.avatar:
        person["image"] = _absolute(request, profile.avatar.url)

    same_as = [
        url for url in (
            profile.website_url, profile.instagram_url, profile.telegram_url,
            profile.youtube_url, profile.twitter_url,
        ) if url
    ]
    if same_as:
        person["sameAs"] = same_as

    data = {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "mainEntity": person,
        "url": request.build_absolute_uri(),
    }
    return json.dumps(data, ensure_ascii=False)
