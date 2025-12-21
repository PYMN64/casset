from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import UserProfile
from core.models import PlatformSetting
from tracks.models import Track
from .models import DailyTrackStat, FraudFlag, PlayEvent
from .utils import ip_hash, ua_hash


def _rate_limited(request) -> bool:
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


def _is_track_playable(track: Track, user) -> bool:
    if track.status != Track.Status.APPROVED:
        return False
    if track.visibility == Track.Visibility.PRIVATE and track.creator_id != getattr(user, "id", None):
        return False
    return True


@require_POST
def register_play(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "auth_required"}, status=401)

    if _rate_limited(request):
        try:
            FraudFlag.objects.create(
                user=request.user,
                flag_type=FraudFlag.FlagType.PLAY_BURST,
                score=1,
            )
        except Exception:
            pass
        return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)

    track_id = request.POST.get("track_id")
    if not track_id:
        return JsonResponse({"ok": False, "error": "missing_track_id"}, status=400)

    try:
        track = Track.objects.get(id=track_id)
    except Track.DoesNotExist:
        return JsonResponse({"ok": False, "error": "track_not_found"}, status=404)

    user = request.user
    if not _is_track_playable(track, user):
        return JsonResponse({"ok": False, "error": "not_allowed"}, status=403)

    iph = ip_hash(request)
    uah = ua_hash(request)
    day_key = date.today().isoformat()

    created = False
    try:
        with transaction.atomic():
            PlayEvent.objects.create(
                track=track,
                user=user,
                ip_hash=iph,
                ua_hash=uah,
                day_key=day_key,
            )
            Track.objects.filter(id=track.id).update(play_count=F("play_count") + 1)
            DailyTrackStat.objects.update_or_create(
                track=track,
                day=timezone.now().date(),
                defaults={},
            )
            DailyTrackStat.objects.filter(track=track, day=timezone.now().date()).update(
                plays=F("plays") + 1,
                unique_plays=F("unique_plays") + 1,
            )
            created = True
    except IntegrityError:
        created = False
        try:
            FraudFlag.objects.create(
                user=user,
                track=track,
                flag_type=FraudFlag.FlagType.REPEATED_IP,
                score=1,
                note="duplicate play per ip/day",
            )
        except Exception:
            pass

    track.refresh_from_db(fields=["play_count"])
    return JsonResponse({"ok": True, "counted": created, "play_count": track.play_count})


@require_POST
def register_progress(request):
    """Award 1 point to creator when listener reaches threshold percent."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "auth_required"}, status=401)

    track_id = request.POST.get("track_id")
    progress = request.POST.get("progress")
    if not track_id or progress is None:
        return JsonResponse({"ok": False, "error": "missing_params"}, status=400)
    try:
        progress = float(progress)
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad_progress"}, status=400)

    setting = PlatformSetting.get_solo()
    threshold = float(setting.playback_threshold_ratio())

    if progress > 1.0:
        progress = progress / 100.0
    if progress < threshold:
        return JsonResponse({"ok": True, "awarded": False})

    try:
        track = Track.objects.select_related("creator").get(id=track_id)
    except Track.DoesNotExist:
        return JsonResponse({"ok": False, "error": "track_not_found"}, status=404)
    if not _is_track_playable(track, request.user):
        return JsonResponse({"ok": False, "error": "not_allowed"}, status=403)

    iph = ip_hash(request)
    day_key = date.today().isoformat()

    pe = PlayEvent.objects.filter(track=track, ip_hash=iph, day_key=day_key).first()
    if not pe:
        return JsonResponse({"ok": False, "error": "play_not_registered"}, status=409)

    if PlayEvent.objects.filter(
        track=track,
        user=request.user,
        day_key=day_key,
        point_awarded=True,
    ).exists():
        return JsonResponse({"ok": True, "awarded": False})

    if pe.point_awarded:
        return JsonResponse({"ok": True, "awarded": False})

    with transaction.atomic():
        updated = PlayEvent.objects.filter(id=pe.id, point_awarded=False).update(point_awarded=True)
        if updated:
            UserProfile.objects.filter(user=track.creator).update(points=F("points") + 1)
            DailyTrackStat.objects.update_or_create(
                track=track,
                day=timezone.now().date(),
                defaults={},
            )
            DailyTrackStat.objects.filter(track=track, day=timezone.now().date()).update(
                points_awarded=F("points_awarded") + 1,
            )

    return JsonResponse({"ok": True, "awarded": bool(updated)})
