"""plays/views.py — Play registration API endpoints.

Views are intentionally thin: they only handle HTTP concerns (auth, input
parsing, response formatting). All business logic lives in services.py.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from tracks.models import Track

from .models import FraudFlag, PlayEvent
from .services import get_creator_stats_series, start_playback_session, try_award_point
from .utils import ip_hash, ua_hash

logger = logging.getLogger("casset.plays")


def _is_playable(track: Track) -> bool:
    """A play/point may only be registered against approved, non-private
    content. Without this, anyone who knows/guesses a track_id could
    register plays (and earn the creator points) against another
    creator's draft or private track."""
    return (
        track.status == Track.Status.APPROVED
        and track.visibility != Track.Visibility.PRIVATE
    )


def _today_key() -> str:
    """Canonical day bucket for play events.

    Uses the project's local timezone (TIME_ZONE), not the server's OS date,
    so a listener's "today" matches what they see in the UI and what the
    IP-cap query in services.py compares against.
    """
    return timezone.localdate().isoformat()


# ---------------------------------------------------------------------------
# Rate limiting (cheap in-memory guard, first line of defence)
# ---------------------------------------------------------------------------

def _rate_limited(request) -> bool:
    """Return True if this IP has exceeded the burst play rate limit.

    Limit: 5 play requests per 10 seconds per IP.
    Uses Django cache (in-memory in dev, Redis in prod).
    """
    try:
        from django.core.cache import cache
    except Exception:
        return False

    key = f"rl:play:{ip_hash(request)}"
    cur = cache.get(key, 0)
    if cur >= 5:
        return True
    cache.set(key, cur + 1, timeout=10)
    return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@require_POST
def register_play(request):
    """Register one play event for a track.

    Called by the player as soon as playback starts. Records a PlayEvent
    (unique per track/IP/day) and increments the track play_count cache.
    Points are NOT awarded here — that happens in register_progress().

    POST params:
        track_id (int): ID of the track being played.

    Returns JSON:
        {ok, counted, play_count}
    """
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "auth_required"}, status=401)

    if _rate_limited(request):
        iph = ip_hash(request)
        logger.warning("Rate limit hit ip=%s user=%s", iph[:8], request.user.pk)
        try:
            FraudFlag.objects.create(
                user=request.user,
                ip_hash=iph,
                flag_type=FraudFlag.FlagType.PLAY_BURST,
                score=1,
                note="Rate limit exceeded on register_play.",
            )
        except Exception:
            pass
        return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)

    track_id = request.POST.get("track_id")
    if not track_id:
        return JsonResponse({"ok": False, "error": "missing_track_id"}, status=400)

    try:
        track = Track.objects.get(id=track_id)
    except (Track.DoesNotExist, ValueError):
        return JsonResponse({"ok": False, "error": "track_not_found"}, status=404)

    if not _is_playable(track):
        return JsonResponse({"ok": False, "error": "track_not_playable"}, status=403)

    iph = ip_hash(request)
    uah = ua_hash(request)
    day_key = _today_key()

    created = False
    try:
        with transaction.atomic():
            PlayEvent.objects.create(
                track=track,
                user=request.user,
                ip_hash=iph,
                ua_hash=uah,
                day_key=day_key,
            )
            Track.objects.filter(id=track.id).update(play_count=F("play_count") + 1)
            created = True
    except IntegrityError:
        # UniqueConstraint: same IP already played this track today. Not an error.
        created = False
    except Exception as exc:
        logger.exception("register_play error track=%s: %s", track_id, exc)
        return JsonResponse({"ok": False, "error": "server_error"}, status=500)

    track.refresh_from_db(fields=["play_count"])

    # Record this playback attempt for fraud-signal granularity (S11) —
    # deliberately not deduped like PlayEvent, see plays/services.py.
    pe = PlayEvent.objects.filter(
        track=track, user=request.user, ip_hash=iph, day_key=day_key
    ).first()
    try:
        start_playback_session(track=track, user=request.user, ip_hash=iph, ua_hash=uah, play_event=pe)
    except Exception:
        logger.exception("start_playback_session failed track=%s", track_id)

    if created:
        # check_and_notify_milestone() existed since the Notification app was
        # built but was never actually called from anywhere — dead code.
        # This is the one real place a play count changes, so it's the
        # correct (and only) call site.
        try:
            from notifications.services import check_and_notify_milestone
            check_and_notify_milestone(track=track)
        except Exception:
            logger.exception("check_and_notify_milestone failed track=%s", track.id)

    return JsonResponse({"ok": True, "counted": created, "play_count": track.play_count})


@require_POST
def register_progress(request):
    """Report playback progress and attempt to award a point to the creator.

    Called by the player when progress reaches or exceeds the threshold.
    The frontend may call this multiple times; only the first qualifying
    call awards a point (subsequent calls are idempotent).

    POST params:
        track_id (int):   ID of the track being played.
        progress (float): Playback progress as 0..1 ratio OR 0..100 percent.

    Returns JSON:
        {ok, awarded, reason}
    """
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "auth_required"}, status=401)

    track_id = request.POST.get("track_id")
    raw_progress = request.POST.get("progress")

    if not track_id or raw_progress is None:
        return JsonResponse({"ok": False, "error": "missing_params"}, status=400)

    try:
        progress = float(raw_progress)
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "bad_progress"}, status=400)

    # Normalise: frontend may send 0..100 or 0..1
    if progress > 1.0:
        progress = progress / 100.0
    progress = max(0.0, min(1.0, progress))

    try:
        track = Track.objects.select_related("creator").get(id=track_id)
    except (Track.DoesNotExist, ValueError):
        return JsonResponse({"ok": False, "error": "track_not_found"}, status=404)

    if not _is_playable(track):
        return JsonResponse({"ok": False, "error": "track_not_playable"}, status=403)

    iph = ip_hash(request)
    uah = ua_hash(request)
    day_key = _today_key()

    result = try_award_point(
        track=track,
        ip_hash=iph,
        day_key=day_key,
        progress_ratio=progress,
        listener_user=request.user,
        ua_hash=uah,
    )

    return JsonResponse({
        "ok": True,
        "awarded": result.awarded,
        "reason": result.reason,
    })


@require_GET
def api_creator_stats(request):
    """Plays/points series for the logged-in creator's own tracks, sourced
    from DailyTrackStat (S11) — for the studio dashboard's trend chart.

    GET params:
        range (str): "daily" (last 30 days), "weekly" (last 12 weeks), or
            "monthly" (last 12 months). Defaults to "daily".

    Returns JSON:
        {ok, range, series: [{label, plays, unique_plays, points}, ...]}
    """
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "auth_required"}, status=401)

    granularity = request.GET.get("range", "daily")
    if granularity not in ("daily", "weekly", "monthly"):
        granularity = "daily"

    series = get_creator_stats_series(creator=request.user, granularity=granularity)
    return JsonResponse({"ok": True, "range": granularity, "series": series})
