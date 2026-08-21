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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from django.db import transaction
from django.db.models import DurationField, ExpressionWrapper, F
from django.utils import timezone as dj_timezone

from accounts.models import UserProfile
from core.models import PlatformSetting

from .models import FraudFlag, PlaybackSession, PlayEvent, PointLedger

logger = logging.getLogger("casset.plays")

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

# Max awards a single IP hash can earn in one calendar day across all tracks.
_DEFAULT_IP_DAILY_AWARD_CAP = 50

# Minimum ratio of track duration that must have elapsed before we trust
# a progress report. Guards against bots sending fake progress instantly.
_MIN_ELAPSED_RATIO = 0.50

# Anti-fraud signals (S11) — heuristic starting thresholds, tunable later.
# Burst: how many PlaybackSessions one IP has started in a short window.
_BURST_WINDOW_SECONDS = 60
_BURST_SOFT_THRESHOLD = 8    # flagged for review only, still allowed to award
_BURST_HARD_THRESHOLD = 15   # blocked outright

# Repeated very-short sessions from the same listener (bot-like replay spam).
_SHORT_SESSION_SECONDS = 3
_SHORT_SESSION_WINDOW_MINUTES = 5
_SHORT_SESSION_HARD_COUNT = 3


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


@dataclass
class FraudSignalResult:
    hard_block: bool
    note: str = field(default="")


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
    ua_hash: str = "",
) -> AwardResult:
    """Attempt to award 1 point to track.creator for a qualifying play.

    Always returns an AwardResult. Never raises.
    """
    setting = PlatformSetting.get_solo()
    threshold = setting.playback_threshold_ratio()

    session = _touch_session(
        track=track, listener_user=listener_user, ip_hash=ip_hash,
        ua_hash=ua_hash, progress_ratio=progress_ratio,
    )

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
            session=session,
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
# PlaybackSession lifecycle
# ---------------------------------------------------------------------------

def start_playback_session(
    *, track, user, ip_hash: str, ua_hash: str, play_event=None, source: str = "web"
) -> PlaybackSession:
    """Record one playback attempt. Called once per register_play() call —
    deliberately NOT deduped the way PlayEvent is: fraud signals need
    attempt-level granularity, since a bot hammering play many times a
    minute looks identical to a single legitimate play once daily dedup
    collapses it into one PlayEvent row."""
    return PlaybackSession.objects.create(
        track=track, user=user, ip_hash=ip_hash, ua_hash=ua_hash,
        play_event=play_event, source=source,
    )


def _touch_session(
    *, track, listener_user, ip_hash: str, ua_hash: str, progress_ratio: float
) -> PlaybackSession:
    """Find the listener's most recent PlaybackSession for this track and
    record this progress report against it. If none exists at all (a
    progress report with no prior register_play() call — a broken client or
    direct API probing), create a minimal flagged one so the report is still
    auditable, mirroring the BLOCKED_NO_EVENT gate below but at the session
    level."""
    session = (
        PlaybackSession.objects
        .filter(track=track, user=listener_user)
        .order_by("-started_at")
        .first()
    )
    if session is None:
        session = PlaybackSession.objects.create(
            track=track, user=listener_user, ip_hash=ip_hash, ua_hash=ua_hash,
            status=PlaybackSession.Status.FLAGGED,
            disqualify_reason="no_prior_session",
            source="progress_fallback",
        )

    session.max_progress_ratio = max(session.max_progress_ratio, progress_ratio)
    session.last_seen_at = dj_timezone.now()
    session.save(update_fields=["max_progress_ratio", "last_seen_at"])
    return session


def _close_session(session: PlaybackSession, *, status: str, reason: str = "") -> None:
    session.status = status
    session.disqualify_reason = reason[:120]
    session.ended_at = dj_timezone.now()
    session.save(update_fields=["status", "disqualify_reason", "ended_at"])


# ---------------------------------------------------------------------------
# Anti-fraud signals (S11)
#
# Constitution: client-reported progress alone is never proof of a valid
# play, and fraud detection must affect Qualified Play (block or flag for
# review) rather than unilaterally banning a user. These signals only ever
# write an auditable PointLedger/FraudFlag row and (for hard blocks) close
# the PlaybackSession as FLAGGED — they never touch User.is_active or any
# account-level state (that stays a staff decision, moderation/services.py).
# ---------------------------------------------------------------------------

def evaluate_fraud_signals(*, session: PlaybackSession, ip_hash: str, listener_user) -> FraudSignalResult:
    now = dj_timezone.now()

    # Signal A — abnormal play-attempt rate from one IP, regardless of
    # account (catches a bot rotating accounts behind one connection).
    burst_window_start = now - timedelta(seconds=_BURST_WINDOW_SECONDS)
    ip_session_count = PlaybackSession.objects.filter(
        ip_hash=ip_hash, started_at__gte=burst_window_start,
    ).count()

    if ip_session_count >= _BURST_HARD_THRESHOLD:
        note = f"ip_burst count={ip_session_count} window={_BURST_WINDOW_SECONDS}s"
        _flag_fraud(
            user=listener_user, track=session.track, ip_hash=ip_hash,
            flag_type=FraudFlag.FlagType.PLAY_BURST, score=8, note=note,
        )
        return FraudSignalResult(hard_block=True, note=note)

    if ip_session_count >= _BURST_SOFT_THRESHOLD:
        note = f"ip_burst count={ip_session_count} window={_BURST_WINDOW_SECONDS}s"
        _flag_fraud(
            user=listener_user, track=session.track, ip_hash=ip_hash,
            flag_type=FraudFlag.FlagType.PLAY_BURST, score=3, note=note,
        )
        # Soft signal only — surfaced to staff, does not block this award.

    # Signal B — repeated very-short sessions from the same listener (play,
    # immediately abandon, repeat — a bot-like replay pattern). Only counts
    # sessions that already concluded (ended_at set), so it builds on top of
    # gates that already closed a session (e.g. the time gate below), not on
    # sessions still legitimately in progress.
    short_window_start = now - timedelta(minutes=_SHORT_SESSION_WINDOW_MINUTES)
    recent_short = (
        PlaybackSession.objects
        .filter(user=listener_user, started_at__gte=short_window_start, ended_at__isnull=False)
        .annotate(
            length=ExpressionWrapper(
                F("ended_at") - F("started_at"), output_field=DurationField()
            )
        )
        .filter(length__lt=timedelta(seconds=_SHORT_SESSION_SECONDS))
        .count()
    )

    if recent_short >= _SHORT_SESSION_HARD_COUNT:
        note = f"short_sessions count={recent_short} window={_SHORT_SESSION_WINDOW_MINUTES}m"
        _flag_fraud(
            user=listener_user, track=session.track, ip_hash=ip_hash,
            flag_type=FraudFlag.FlagType.TIME_FRAUD, score=6, note=note,
        )
        return FraudSignalResult(hard_block=True, note=note)

    return FraudSignalResult(hard_block=False)


# ---------------------------------------------------------------------------
# Internal pipeline
# ---------------------------------------------------------------------------

def _run_gating_pipeline(
    *, track, ip_hash, day_key, progress_ratio, listener_user, setting, session: PlaybackSession
) -> AwardResult:
    """Run all gates and write the appropriate PointLedger entry."""

    creator = track.creator

    # Gate 0 - fraud signals (S11). Only evaluated for sessions still open —
    # a session already resolved (qualified/flagged) doesn't need re-scoring
    # on every idempotent duplicate progress ping.
    if session.status == PlaybackSession.Status.OPEN:
        fraud = evaluate_fraud_signals(session=session, ip_hash=ip_hash, listener_user=listener_user)
        if fraud.hard_block:
            logger.warning(
                "BLOCKED_FRAUD_SIGNAL track=%s ip=%s reason=%s",
                track.pk, ip_hash[:8], fraud.note,
            )
            _write_ledger(
                user=creator, delta=0,
                reason=PointLedger.Reason.BLOCKED_FRAUD_SIGNAL,
                play_event=None, track=track, ip_hash=ip_hash, note=fraud.note,
            )
            _close_session(session, status=PlaybackSession.Status.FLAGGED, reason=fraud.note)
            return AwardResult(
                awarded=False, reason=PointLedger.Reason.BLOCKED_FRAUD_SIGNAL, note=fraud.note
            )

    # Gate 1 - PlayEvent must exist for this specific listener (not just
    # this IP — two different users can share an IP/day/track now that
    # PlayEvent uniqueness includes `user`, see plays/models.py).
    pe = (
        PlayEvent.objects
        .filter(track=track, user=listener_user, ip_hash=ip_hash, day_key=day_key)
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
        if session.status == PlaybackSession.Status.OPEN:
            _close_session(session, status=PlaybackSession.Status.FLAGGED,
                            reason=PointLedger.Reason.BLOCKED_NO_EVENT)
        return AwardResult(awarded=False, reason=PointLedger.Reason.BLOCKED_NO_EVENT)

    # Gate 2 - Not already awarded
    if pe.point_awarded:
        return AwardResult(awarded=False, reason=PointLedger.Reason.BLOCKED_DUPLICATE)

    # Gate 3 - Time gate
    duration = getattr(track, "duration_seconds", 0) or 0
    if duration > 0:
        now_utc = datetime.now(UTC)
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
            if session.status == PlaybackSession.Status.OPEN:
                _close_session(session, status=PlaybackSession.Status.FLAGGED,
                                reason=PointLedger.Reason.BLOCKED_TIME)
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
        # Not a per-session fraud pattern (the cap is platform/IP-wide, not
        # this session's fault) — leave the session OPEN, un-flagged.
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

        if session.status == PlaybackSession.Status.OPEN:
            session.status = PlaybackSession.Status.QUALIFIED
            session.ended_at = dj_timezone.now()
            session.play_event = pe
            session.save(update_fields=["status", "ended_at", "play_event"])

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
    play_event: PlayEvent | None,
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
