from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from core.models import PlatformSetting
from plays.models import PlayEvent
from tracks.models import Track


@dataclass
class Rule:
    key: str
    title: str
    current: int
    required: int

    @property
    def ok(self) -> bool:
        return self.current >= self.required

    @property
    def remaining(self) -> int:
        return max(0, self.required - self.current)


def compute_listener_rules(user):
    plays = PlayEvent.objects.filter(user=user).count()
    return [
        Rule("listener_plays", "Listen to 100 plays", plays, 100),
    ]


def compute_creator_rules(user):
    setting = PlatformSetting.get_solo()
    since = timezone.now() - timedelta(days=30)

    approved_tracks = Track.objects.filter(creator=user, status=Track.Status.APPROVED).count()
    recent_plays = PlayEvent.objects.filter(track__creator=user, created_at__gte=since).count()
    recent_points = PlayEvent.objects.filter(
        track__creator=user,
        point_awarded=True,
        created_at__gte=since,
    ).count()

    rules = [
        Rule("creator_tracks", "3 approved tracks", approved_tracks, 3),
    ]

    if int(setting.min_valid_plays_30d or 0) > 0:
        rules.append(Rule("creator_plays_30d", "Valid plays (30d)", recent_plays, int(setting.min_valid_plays_30d)))
    if int(setting.min_payout_points_30d or 0) > 0:
        rules.append(Rule("creator_points_30d", "Points (30d)", recent_points, int(setting.min_payout_points_30d)))

    return rules


def compute_eligibility(user):
    listener_rules = compute_listener_rules(user)
    creator_rules = compute_creator_rules(user)

    listener_ok = all(r.ok for r in listener_rules)
    creator_ok = all(r.ok for r in creator_rules) if creator_rules else False

    pro_eligible = listener_ok or creator_ok

    all_rules = listener_rules + creator_rules
    total = len(all_rules)
    done = sum(1 for r in all_rules if r.ok)
    progress_pct = int((done / total) * 100) if total else 0

    return {
        "pro_eligible": pro_eligible,
        "progress_pct": progress_pct,
        "listener_rules": listener_rules,
        "creator_rules": creator_rules,
    }
