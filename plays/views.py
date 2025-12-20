from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from tracks.models import Track
from accounts.models import UserProfile  # ✅ فقط همینجا از accounts می‌گیریم
from .models import PlayEvent, FraudFlag
from .utils import ip_hash, ua_hash
from core.models import PlatformSetting


def _rate_limited(request) -> bool:
    # خیلی سبک: هر IP در 10 ثانیه حداکثر 5 درخواست play
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


@require_POST
def register_play(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "auth_required"}, status=401)

    if _rate_limited(request):
        # log a soft fraud signal
        try:
            FraudFlag.objects.create(user=request.user, flag_type=FraudFlag.FlagType.PLAY_BURST, score=1)
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
            created = True
            # Points awarding is handled via progress endpoint (>= threshold).

    except IntegrityError:
        created = False

    track.refresh_from_db(fields=["play_count"])
    return JsonResponse({"ok": True, "counted": created, "play_count": track.play_count})


@require_POST
def register_progress(request):
    """Award 1 point to creator when listener reaches threshold percent.

    Frontend should call this once per play when progress >= threshold.
    """
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

    # Frontend may send 0..1 ratio or 0..100 percent. Normalize.
    if progress > 1.0:
        progress = progress / 100.0

    if progress < threshold:
        return JsonResponse({"ok": True, "awarded": False})

    try:
        track = Track.objects.select_related("creator").get(id=track_id)
    except Track.DoesNotExist:
        return JsonResponse({"ok": False, "error": "track_not_found"}, status=404)

    iph = ip_hash(request)
    day_key = date.today().isoformat()

    # Find existing play event for this user/ip/day
    pe = PlayEvent.objects.filter(track=track, ip_hash=iph, day_key=day_key).first()
    if not pe:
        return JsonResponse({"ok": False, "error": "play_not_registered"}, status=409)

    if pe.point_awarded:
        return JsonResponse({"ok": True, "awarded": False})

    # Award to creator only
    with transaction.atomic():
        updated = PlayEvent.objects.filter(id=pe.id, point_awarded=False).update(point_awarded=True)
        if updated:
            UserProfile.objects.filter(user=track.creator).update(points=F("points") + 1)

    return JsonResponse({"ok": True, "awarded": bool(updated)})
