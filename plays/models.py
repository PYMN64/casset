import logging

from django.conf import settings
from django.db import models
from django.db.models import Sum

logger = logging.getLogger("casset.plays")


class PlayEvent(models.Model):
    """One unique play per (track, user, ip_hash, day).

    This is the raw event source. play_count on Track is a derived cache.
    All point decisions are made in register_progress(), not here.

    `user` is part of the uniqueness key (not just ip_hash/day) so that two
    different logged-in listeners behind the same IP/NAT (same office,
    campus, or mobile carrier CGNAT) each get their own PlayEvent instead of
    the second one silently colliding with the first's row. `user` is
    nullable for schema flexibility, but every write path currently
    requires authentication (see plays/views.py), so it is never actually
    null in practice today.
    """

    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="play_events"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="play_events",
    )
    ip_hash = models.CharField(max_length=64)       # sha256(salt|ip)
    ua_hash = models.CharField(max_length=64, blank=True)  # sha256(salt|ua)
    day_key = models.CharField(max_length=10)       # YYYY-MM-DD
    created_at = models.DateTimeField(auto_now_add=True)
    point_awarded = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["track", "day_key"]),
            models.Index(fields=["ip_hash", "day_key"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["track", "user", "ip_hash", "day_key"],
                name="uniq_play_track_user_ip_day",
            )
        ]

    def __str__(self):
        return f"PlayEvent(track={self.track_id}, day={self.day_key})"


class PointLedger(models.Model):
    """Immutable double-entry ledger for all point transactions.

    Design principles
    -----------------
    * Every point change — award or block — gets one row. Nothing is ever
      deleted or updated; the audit trail is permanent.
    * `delta` is signed: positive = award, negative = deduction (future).
    * `UserProfile.points` is a *derived cache* = SUM(delta) for that user.
      Use `recalculate_points` management command to rebuild it if drift occurs.
    * A blocked play is recorded with delta=0 and reason=BLOCKED_* so staff
      can see exactly why a point was NOT awarded.

    Reason codes
    ------------
    PLAY_REWARD      — normal award: listener reached playback threshold
    PAYOUT_DEDUCTION — creator payout approved (billing/services.py::approve_payout)
    BLOCKED_NO_EVENT — progress sent but no matching PlayEvent found
    BLOCKED_TIME     — progress too fast (bot signal)
    BLOCKED_IP_LIMIT — IP exceeded daily award cap
    BLOCKED_DUPLICATE— point already awarded for this play
    """

    class Reason(models.TextChoices):
        # Positive
        PLAY_REWARD = "play_reward", "Play reward"
        # Negative — first (and so far only) real use of the signed `delta`
        # the class docstring above always promised ("future").
        PAYOUT_DEDUCTION = "payout_deduction", "Payout deduction"
        # Blocked (delta=0, logged for audit)
        BLOCKED_NO_EVENT   = "blocked_no_event",   "Blocked: no play event"
        BLOCKED_TIME       = "blocked_time",       "Blocked: too fast"
        BLOCKED_IP_LIMIT   = "blocked_ip_limit",   "Blocked: IP daily cap"
        BLOCKED_DUPLICATE  = "blocked_duplicate",  "Blocked: already awarded"
        BLOCKED_FRAUD_SIGNAL = "blocked_fraud_signal", "Blocked: fraud signal (S11)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="point_ledger",
        help_text="Creator who received (or was blocked from receiving) the point.",
    )
    delta = models.SmallIntegerField(
        default=0,
        help_text="+1 for award, 0 for blocked events (full audit trail).",
    )
    reason = models.CharField(max_length=32, choices=Reason.choices)
    play_event = models.OneToOneField(
        PlayEvent,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ledger_entry",
        help_text="The PlayEvent that triggered this entry (null for manual entries).",
    )
    # Snapshot fields — stored at write-time so the ledger is self-contained
    # even if the related track/user is later deleted.
    track_id_snapshot = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Track ID at award time (denormalised for audit durability).",
    )
    ip_hash_snapshot = models.CharField(
        max_length=64, blank=True,
        help_text="IP hash at award time (denormalised).",
    )
    note = models.CharField(
        max_length=300, blank=True,
        help_text="Free-text detail added by system or staff.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="ledger_user_ts"),
            models.Index(fields=["reason", "created_at"], name="ledger_reason_ts"),
            models.Index(fields=["ip_hash_snapshot", "created_at"], name="ledger_ip_ts"),
        ]
        verbose_name = "Point ledger entry"
        verbose_name_plural = "Point ledger"

    def __str__(self):
        return (
            f"PointLedger(user={self.user_id}, "
            f"delta={self.delta:+d}, reason={self.reason})"
        )

    @classmethod
    def total_for_user(cls, user) -> int:
        """Sum all delta values for a user — the canonical point balance."""
        result = cls.objects.filter(user=user).aggregate(total=Sum("delta"))
        return result["total"] or 0


class DailyTrackStat(models.Model):
    """Pre-aggregated daily stats for fast dashboards.

    Computed from PlayEvent + PointLedger via management command.
    Never write to this table directly — always re-derive.
    """

    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="daily_stats"
    )
    day = models.DateField()
    plays = models.PositiveIntegerField(default=0)
    unique_plays = models.PositiveIntegerField(default=0)
    points_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["track", "day"], name="uniq_daily_track_day"
            )
        ]
        indexes = [
            models.Index(fields=["track", "day"], name="plays_dts_track_day"),
            models.Index(fields=["day"], name="plays_dts_day"),
        ]
        ordering = ["-day"]

    def __str__(self) -> str:
        return f"DailyTrackStat(track={self.track_id}, day={self.day})"


class PlaybackSession(models.Model):
    """One real playback attempt — from the player's first "play" tap to
    however it resolved (qualified, flagged as a fraud signal, or simply
    abandoned below the award threshold).

    Distinct from `PlayEvent` (a once-per-day dedup row that decides
    point-award eligibility): a listener can generate several
    PlaybackSessions for the same track on the same day (replays, seeking
    back to the start, a bot hammering play), and that finer granularity is
    exactly what the fraud signals in services.py need — burst/short-session
    detection is meaningless at PlayEvent's once-a-day resolution. This
    model does not replace PlayEvent or its uniqueness constraint; it is an
    additional, more granular audit trail layered on top of it (S11).
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        QUALIFIED = "qualified", "Qualified (point awarded)"
        FLAGGED = "flagged", "Flagged (fraud signal / anomaly)"
        CLOSED = "closed", "Closed (concluded without qualifying)"

    track = models.ForeignKey(
        "tracks.Track", on_delete=models.CASCADE, related_name="playback_sessions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="playback_sessions",
    )
    play_event = models.ForeignKey(
        PlayEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        help_text="The daily-dedup PlayEvent this attempt counted toward, if any.",
    )

    ip_hash = models.CharField(max_length=64)
    ua_hash = models.CharField(max_length=64, blank=True)
    source = models.CharField(
        max_length=32, default="web",
        help_text="Where the play originated: web, embed, api, progress_fallback, backfill.",
    )

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    disqualify_reason = models.CharField(
        max_length=120, blank=True,
        help_text="Set when status=flagged: which signal/gate rejected this session.",
    )

    max_progress_ratio = models.FloatField(default=0.0)

    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["track", "user", "started_at"], name="session_track_user_ts"),
            models.Index(fields=["ip_hash", "started_at"], name="session_ip_ts"),
            models.Index(fields=["status", "started_at"], name="session_status_ts"),
        ]

    def __str__(self) -> str:
        return f"PlaybackSession(track={self.track_id}, user={self.user_id}, status={self.status})"


class FraudFlag(models.Model):
    """Soft fraud signal — informational only, no auto-ban.

    Staff reviews these in admin. Blocking happens at award-time in services.py
    (recorded in PointLedger with delta=0), not here.
    """

    class FlagType(models.TextChoices):
        PLAY_BURST   = "play_burst",   "Play burst (rate limit)"
        TIME_FRAUD   = "time_fraud",   "Progress too fast"
        IP_DAY_LIMIT = "ip_day_limit", "IP daily award cap reached"
        OTHER        = "other",        "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fraud_flags",
    )
    track = models.ForeignKey(
        "tracks.Track",
        on_delete=models.CASCADE,
        related_name="fraud_flags",
        null=True,
        blank=True,
    )
    ip_hash = models.CharField(max_length=64, blank=True)
    flag_type = models.CharField(max_length=32, choices=FlagType.choices)
    score = models.PositiveIntegerField(
        default=1,
        help_text="Severity score. Higher = more suspicious.",
    )
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["flag_type", "created_at"]),
            models.Index(fields=["ip_hash", "created_at"]),
        ]

    def __str__(self):
        return f"FraudFlag({self.flag_type}, track={self.track_id})"
