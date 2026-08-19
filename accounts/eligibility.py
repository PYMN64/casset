from dataclasses import dataclass

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
    # play معتبر: هر PlayEvent که ثبت شده
    plays = PlayEvent.objects.filter(user=user).count()

    return [
        Rule("listener_plays", "حداقل 100 پخش معتبر", plays, 100),
    ]


def compute_creator_rules(user):
    approved_tracks = Track.objects.filter(creator=user, status=Track.Status.APPROVED).count()
    total_track_plays = Track.objects.filter(creator=user, status=Track.Status.APPROVED).values_list("play_count", flat=True)
    total_track_plays = sum(total_track_plays) if total_track_plays else 0

    return [
        Rule("creator_tracks", "حداقل 3 ترک تایید‌شده", approved_tracks, 3),
        Rule("creator_plays", "حداقل 50 پخش روی ترک‌ها", total_track_plays, 50),
    ]


def compute_eligibility(user):
    listener_rules = compute_listener_rules(user)
    creator_rules = compute_creator_rules(user)

    listener_ok = all(r.ok for r in listener_rules)
    creator_ok = all(r.ok for r in creator_rules)

    # soft gate: اگر یکی از مسیرها ok شد، Pro Eligible میشه
    pro_eligible = listener_ok or creator_ok

    # درصد پیشرفت ساده (برای UX)
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
