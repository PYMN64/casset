"""plays/services.py — Point award logic for Casset.

This module is the single place where points are awarded or blocked.
Views call these functions; they never touch PointLedger or UserProfile.points
directly.

Gating pipeline (in order)
--------------------------
1. PlayEvent exists for (track, ip_hash, day_key)
   -> if not: block with BLOCKED_NO_EVENT
2. Not already awarded (point_awarded=False)
   -> if already: block with BLOCKED_DUPLICATE
3. Time gate: elapsed >= track.duration * _MIN_ELAPSED_RATIO
   -> if too fast: block with BLOCKED_TIME + FraudFlag(TIME_FRAUD)
4. IP daily award cap not exceeded
   -> if over cap: block with BLOCKED_IP_LIMIT + FraudFlag(IP_DAY_LIMIT)
5. Award: PointLedger(delta=+1) + UserProfile.points++ (cache)

All blocked paths write a PointLedger row with delta=0 so the audit trail
is complete and staff can understand every decision.
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from django.db import transaction
from django.db.models import F
from django.utils import timezone as dj_timezone

from accounts.models import UserProfile
from core.models import PlatformSetting
from .models import FraudFlag, PlayEvent, PointLedger

logger = logging.getLogger("casset.plays")

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

# Max awards a single IP hash can earn in one calendar day across all tracks.
_DEFAULT_IP_DAILY_AWARD_CAP = 50

# Minimum ratio of track duration that must have elapsed before we trust
# a progress report. Guards against bots sending fake progress instantly.
_MIN_ELAPSED_RATIO = 0.50


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AwardResult:
    awarded: bool
    reason: str
    note: str = field(default="")

    @property
    def blocked(self) -> bool:
        return not self.awarded


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def try_award_point(
    *,
    track,
    ip_hash: str,
    day_key: str,
    progress_ratio: float,
    listener_user,
) -> AwardResult:
    """Attempt to award 1 point to track.creator for a qualifying play.

    Always returns an AwardResult. Never raises.
    """
    setting = PlatformSetting.get_solo()
    threshold = setting.playback_threshold_ratio()

    if progress_ratio < threshold:
        return AwardResult(awarded=False, reason="below_threshold")

    try:
        return _run_gating_pipeline(
            track=track,
            ip_hash=ip_hash,
            day_key=day_key,
            progress_ratio=progress_ratio,
            listener_user=listener_user,
            setting=setting,
        )
    except Exception as exc:
        logger.exception(
            "Unexpected error in try_award_point track=%s ip=%s day=%s: %s",
            track.pk, ip_hash[:8], day_key, exc,
        )
        return AwardResult(
            awarded=False,
            reason=PointLedger.Reason.BLOCKED_NO_EVENT,
            note=f"internal error: {type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# Internal pipeline
# ---------------------------------------------------------------------------

def _run_gating_pipeline(
    *, track, ip_hash, day_key, progress_ratio, listener_user, setting
) -> AwardResult:
    """Run all gates and write the appropriate PointLedger entry."""

    creator = track.creator

    # Gate 1 - PlayEvent must exist
    pe = (
        PlayEvent.objects
        .filter(track=track, ip_hash=ip_hash, day_key=day_key)
        .first()
    )
    if pe is None:
        logger.warning(
            "BLOCKED_NO_EVENT track=%s ip=%s day=%s",
            track.pk, ip_hash[:8], day_key,
        )
        _write_ledger(
            user=creator, delta=0,
            reason=PointLedger.Reason.BLOCKED_NO_EVENT,
            play_event=None, track=track, ip_hash=ip_hash,
            note="Progress received without prior PlayEvent registration.",
        )
        return AwardResult(awarded=False, reason=PointLedger.Reason.BLOCKED_NO_EVENT)

    # Gate 2 - Not already awarded
    if pe.point_awarded:
        return AwardResult(awarded=False, reason=PointLedger.Reason.BLOCKED_DUPLICATE)

    # Gate 3 - Time gate
    duration = getattr(track, "duration_seconds", 0) or 0
    if duration > 0:
        now_utc = datetime.now(timezone.utc)
        elapsed = (now_utc - pe.created_at).total_seconds()
        min_elapsed = duration * _MIN_ELAPSED_RATIO

        if elapsed < min_elapsed:
            note = (
                f"elapsed={elapsed:.1f}s min_required={min_elapsed:.1f}s "
                f"duration={duration}s progress={progress_ratio:.2f}"
            )
            logger.warning(
                "BLOCKED_TIME track=%s ip=%s elapsed=%.1fs min=%.1fs",
                track.pk, ip_hash[:8], elapsed, min_elapsed,
            )
            _write_ledger(
                user=creator, delta=0,
                reason=PointLedger.Reason.BLOCKED_TIME,
                play_event=pe, track=track, ip_hash=ip_hash, note=note,
            )
            _flag_fraud(
                user=listener_user, track=track, ip_hash=ip_hash,
                flag_type=FraudFlag.FlagType.TIME_FRAUD, score=3, note=note,
            )
            return AwardResult(
                awarded=False, reason=PointLedger.Reason.BLOCKED_TIME, note=note
            )

    # Gate 4 - IP daily award cap
    #
    # IMPORTANT: `created_at__date` is evaluated in the project's local
    # timezone (TIME_ZONE), so the comparison value must also be the local
    # date. Using datetime.now(timezone.utc).date() here was a real bug:
    # after local midnight but before UTC midnight the two differ by one day,
    # so the cap silently applied to the wrong day.
    cap = _DEFAULT_IP_DAILY_AWARD_CAP
    ip_awards_today = PointLedger.objects.filter(
        ip_hash_snapshot=ip_hash,
        reason=PointLedger.Reason.PLAY_REWARD,
        created_at__date=dj_timezone.localdate(),
    ).count()

    if ip_awards_today >= cap:
        note = f"ip_awards_today={ip_awards_today} cap={cap}"
        logger.warning(
            "BLOCKED_IP_LIMIT track=%s ip=%s today=%d cap=%d",
            track.pk, ip_hash[:8], ip_awards_today, cap,
        )
        _write_ledger(
            user=creator, delta=0,
            reason=PointLedger.Reason.BLOCKED_IP_LIMIT,
            play_event=pe, track=track, ip_hash=ip_hash, note=note,
        )
        _flag_fraud(
            user=listener_user, track=track, ip_hash=ip_hash,
            flag_type=FraudFlag.FlagType.IP_DAY_LIMIT, score=5, note=note,
        )
        return AwardResult(
            awarded=False, reason=PointLedger.Reason.BLOCKED_IP_LIMIT, note=note
        )

    # All gates passed - award atomically
    with transaction.atomic():
        updated = PlayEvent.objects.filter(
            pk=pe.pk, point_awarded=False
        ).update(point_awarded=True)

        if not updated:
            return AwardResult(awarded=False, reason=PointLedger.Reason.BLOCKED_DUPLICATE)

        _write_ledger(
            user=creator, delta=1,
            reason=PointLedger.Reason.PLAY_REWARD,
            play_event=pe, track=track, ip_hash=ip_hash, note="",
        )
        UserProfile.objects.filter(user=creator).update(points=F("points") + 1)

    logger.info(
        "AWARDED track=%s creator=%s ip=%s day=%s",
        track.pk, creator.pk, ip_hash[:8], day_key,
    )
    return AwardResult(awarded=True, reason=PointLedger.Reason.PLAY_REWARD)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_ledger(
    *, user, delta: int, reason: str,
    play_event: Optional[PlayEvent],
    track, ip_hash: str, note: str,
) -> PointLedger:
    return PointLedger.objects.create(
        user=user,
        delta=delta,
        reason=reason,
        play_event=play_event,
        track_id_snapshot=track.pk,
        ip_hash_snapshot=ip_hash,
        note=note,
    )


def _flag_fraud(
    *, user, track, ip_hash: str,
    flag_type: str, score: int, note: str,
) -> None:
    try:
        FraudFlag.objects.create(
            user=user if (user and user.is_authenticated) else None,
            track=track,
            ip_hash=ip_hash,
            flag_type=flag_type,
            score=score,
            note=note,
        )
    except Exception as exc:
        logger.error("Failed to write FraudFlag: %s", exc)
