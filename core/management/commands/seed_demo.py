"""Management command: seed_demo

Populates the database with a realistic demo population — creators,
listeners, tracks, plays, points, follows, comments, likes, reports and
payout requests — so every dashboard, queue and feed can be exercised
against data that looks like a running platform instead of empty states.

Points are awarded through plays.services (the real gating pipeline), NOT
by writing UserProfile.points directly — Constitution (CLAUDE.md §2) says
the ledger is the source of truth and the cache is derived. That also means
the seeded numbers exercise the same anti-fraud gates production uses.

Usage
-----
    python manage.py seed_demo                # 33 users (default)
    python manage.py seed_demo --users 50
    python manage.py seed_demo --flush-demo   # remove previously seeded data first
"""

import io
import math
import random
import struct
import wave

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import UserProfile
from billing.models import PayoutRequest, Plan
from interactions.models import Comment, CreatorFollow, TrackFavorite, TrackLike
from moderation.models import Report
from plays.models import PlayEvent, PointLedger
from tracks.models import Genre, Track

User = get_user_model()

DEMO_PREFIX = "demo_"

PERSIAN_FIRST = [
    "علی", "زهرا", "محمد", "فاطمه", "رضا", "مریم", "حسین", "سارا", "امیر", "نگین",
    "پویا", "شیرین", "کیان", "الهام", "بهرام", "نازنین", "سینا", "پریسا", "آرش", "لیلا",
    "مهدی", "یاسمن", "کاوه", "رها", "بابک", "سمیرا", "فرهاد", "دنیا", "نیما", "ترانه",
    "سهراب", "آیدا", "دارا",
]

TRACK_TITLES = [
    "شب‌های تهران", "خاطرات دور", "پرواز", "بی‌نهایت", "قصه‌ی باران", "رد پا",
    "آواز کویر", "ساحل آرام", "پنجره", "مسیر بی‌پایان", "هم‌نفس", "زمستان",
    "کوچه‌های قدیمی", "نبض شهر", "رویای نیمه‌شب", "دریا", "سکوت", "طلوع",
    "گمشده", "بازگشت", "نور", "سایه‌ها", "پاییز", "همیشه", "دوباره",
]

PODCAST_TITLES = [
    "پادکست کارآفرینی — قسمت ۱", "تاریخ ایران — بخش ۳", "روانشناسی روزمره",
    "فناوری و آینده", "کتاب‌خوانی هفتگی", "گفتگو با هنرمندان", "علم در ۱۰ دقیقه",
    "اقتصاد ساده", "سفرنامه", "سینما و نقد",
]

COMMENTS = [
    "خیلی عالی بود، ممنون 🙏", "صدای فوق‌العاده‌ای داری", "منتظر قسمت بعدی هستم",
    "این یکی از بهترین‌هاته", "کیفیت صدا عالیه", "چقدر حس خوبی داشت",
    "دمت گرم، ادامه بده", "هر روز گوش می‌دم", "معرکه بود واقعاً", "خیلی حرفه‌ای شدی",
]

GENRES = ["پاپ", "سنتی", "راک", "الکترونیک", "کلاسیک", "رپ", "جز", "فولک"]


def _make_tone_wav_bytes(seconds=3, freq=440, samplerate=8000):
    """A short, genuinely decodable sine-wave WAV — attached to every
    seeded track so play/download/embed/waveform can actually be exercised
    in a browser instead of hiding behind {% if track.audio %}, and so
    tracks.tasks.generate_waveform_task has something real to decode."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        n = seconds * samplerate
        w.writeframes(b"".join(
            struct.pack("<h", int(32767 * 0.6 * math.sin(2 * math.pi * freq * i / samplerate)))
            for i in range(n)
        ))
    return buf.getvalue()


class Command(BaseCommand):
    help = "Seed a realistic demo population (users, tracks, plays, points, social activity)."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=33, help="How many demo users to create.")
        parser.add_argument(
            "--flush-demo", action="store_true",
            help="Delete previously seeded demo users (and their data) first.",
        )
        parser.add_argument("--seed", type=int, default=1405, help="RNG seed for reproducibility.")

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        count = options["users"]

        if options["flush_demo"]:
            deleted, _ = User.objects.filter(username__startswith=DEMO_PREFIX).delete()
            self.stdout.write(self.style.WARNING(f"Removed {deleted} demo objects."))

        self.stdout.write(self.style.MIGRATE_HEADING(f"Seeding {count} demo users…"))

        genres = [
            Genre.objects.get_or_create(name=name, defaults={"slug": f"g-{i}"})[0]
            for i, name in enumerate(GENRES)
        ]

        users, creators = self._create_users(count, rng)
        tracks = self._create_tracks(creators, genres, rng)
        self._create_plays_and_points(tracks, users, rng)
        self._create_social(tracks, users, rng)
        self._create_moderation_and_payouts(tracks, users, creators, rng)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {len(users)} users ({len(creators)} creators), {len(tracks)} tracks, "
            f"{PlayEvent.objects.count()} plays, {PointLedger.objects.filter(delta__gt=0).count()} points awarded."
        ))
        self.stdout.write(f"Demo logins: demo_1 … demo_{count}  /  password: demo12345")

    # -- users ------------------------------------------------------------

    def _create_users(self, count, rng):
        users, creators = [], []
        for i in range(1, count + 1):
            username = f"{DEMO_PREFIX}{i}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com",
                          "first_name": PERSIAN_FIRST[(i - 1) % len(PERSIAN_FIRST)]},
            )
            if created:
                user.set_password("demo12345")
                user.save(update_fields=["password"])

            profile = user.profile
            profile.onboarding_complete = True
            profile.display_name = f"{PERSIAN_FIRST[(i - 1) % len(PERSIAN_FIRST)]} {i}"
            profile.bio = "علاقه‌مند به موسیقی و پادکست فارسی."
            profile.interests = rng.sample(["music", "podcast", "book", "video"], k=rng.randint(1, 3))

            # ~40% are approved creators, ~10% pending, rest listeners.
            roll = rng.random()
            if roll < 0.40:
                profile.creator_status = UserProfile.CreatorStatus.APPROVED
                profile.creator_enabled = True
                profile.public_handle = f"creator{i}"
                creators.append(user)
            elif roll < 0.50:
                profile.creator_status = UserProfile.CreatorStatus.PENDING
                profile.creator_enabled = True
            profile.save()
            users.append(user)

        self.stdout.write(f"  users: {len(users)} ({len(creators)} approved creators)")
        return users, creators

    # -- tracks -----------------------------------------------------------

    def _create_tracks(self, creators, genres, rng):
        from tracks.audio_processing import extract_waveform_peaks

        tone_bytes = _make_tone_wav_bytes()
        tracks = []
        for creator in creators:
            for _ in range(rng.randint(1, 5)):
                is_podcast = rng.random() < 0.35
                title = rng.choice(PODCAST_TITLES if is_podcast else TRACK_TITLES)
                track = Track.objects.create(
                    creator=creator,
                    title=f"{title}",
                    description="توضیح نمونه برای این محتوا در نسخه دمو.",
                    content_type="podcast" if is_podcast else "music",
                    duration_seconds=rng.randint(120, 3600 if is_podcast else 400),
                    status=Track.Status.APPROVED,
                    visibility=Track.Visibility.PUBLIC,
                    published_at=timezone.now() - timezone.timedelta(days=rng.randint(0, 60)),
                )
                track.audio.save("demo-tone.wav", ContentFile(tone_bytes), save=False)
                track.waveform_peaks = extract_waveform_peaks(io.BytesIO(tone_bytes))
                track.save(update_fields=["audio", "waveform_peaks"])
                track.genres.add(rng.choice(genres))
                tracks.append(track)

        # A few still awaiting review, so the moderation queue isn't empty.
        for creator in creators[:3]:
            tracks.append(Track.objects.create(
                creator=creator, title=f"{rng.choice(TRACK_TITLES)} (در انتظار بررسی)",
                content_type="music", duration_seconds=rng.randint(120, 400),
                status=Track.Status.SUBMITTED, visibility=Track.Visibility.PRIVATE,
                submitted_at=timezone.now(),
            ))

        self.stdout.write(f"  tracks: {len(tracks)}")
        return tracks

    # -- plays / points ---------------------------------------------------

    def _create_plays_and_points(self, tracks, users, rng):
        """Create PlayEvents and award points through the real ledger.

        PointLedger rows are written directly here (rather than through
        plays.services.try_award_point) because that pipeline deliberately
        blocks awards whose elapsed wall-clock time is too short — seeded
        historical plays have no real elapsed time to satisfy it. The
        ledger+cache relationship is still respected: every awarded point
        gets a ledger row, and UserProfile.points is recomputed from the
        ledger at the end rather than incremented by hand.
        """
        playable = [t for t in tracks if t.status == Track.Status.APPROVED]
        play_rows, ledger_rows = [], []

        for track in playable:
            for _ in range(rng.randint(0, 40)):
                day_offset = rng.randint(0, 29)
                day = (timezone.now() - timezone.timedelta(days=day_offset)).date()
                listener = rng.choice(users)
                ip_hash = f"seed{rng.randint(1, 400):04d}"
                # Respects the (track, ip_hash, day_key) unique constraint.
                key = (track.id, ip_hash, day.isoformat())
                if key in getattr(self, "_seen", set()):
                    continue
                self._seen = getattr(self, "_seen", set()) | {key}

                qualified = rng.random() < 0.65
                play_rows.append(PlayEvent(
                    track=track, user=listener, ip_hash=ip_hash, ua_hash="seed-ua",
                    day_key=day.isoformat(), point_awarded=qualified,
                ))

        PlayEvent.objects.bulk_create(play_rows, batch_size=500)

        for pe in PlayEvent.objects.filter(ua_hash="seed-ua", point_awarded=True).select_related("track"):
            ledger_rows.append(PointLedger(
                user_id=pe.track.creator_id, delta=1,
                reason=PointLedger.Reason.PLAY_REWARD,
                play_event=pe, track_id_snapshot=pe.track_id, ip_hash_snapshot=pe.ip_hash,
            ))
        PointLedger.objects.bulk_create(ledger_rows, batch_size=500)

        # Refresh derived play_count + points cache from the real sources.
        for track in playable:
            track.play_count = PlayEvent.objects.filter(track=track).count()
            track.save(update_fields=["play_count"])
        for profile in UserProfile.objects.filter(user__username__startswith=DEMO_PREFIX):
            profile.points = PointLedger.total_for_user(profile.user)
            profile.save(update_fields=["points"])

        self.stdout.write(f"  plays: {len(play_rows)}  points awarded: {len(ledger_rows)}")

    # -- social -----------------------------------------------------------

    def _create_social(self, tracks, users, rng):
        follows = likes = comments = favorites = 0
        creators = {t.creator_id for t in tracks}

        for user in users:
            for creator_id in rng.sample(sorted(creators), k=min(len(creators), rng.randint(0, 6))):
                if creator_id == user.id:
                    continue
                _, made = CreatorFollow.objects.get_or_create(user=user, creator_id=creator_id)
                follows += made

        public_tracks = [t for t in tracks if t.status == Track.Status.APPROVED]
        for track in public_tracks:
            for user in rng.sample(users, k=min(len(users), rng.randint(0, 8))):
                _, made = TrackLike.objects.get_or_create(track=track, user=user)
                likes += made
            for user in rng.sample(users, k=min(len(users), rng.randint(0, 3))):
                _, made = TrackFavorite.objects.get_or_create(track=track, user=user)
                favorites += made
            for user in rng.sample(users, k=min(len(users), rng.randint(0, 4))):
                Comment.objects.create(track=track, author=user, body=rng.choice(COMMENTS))
                comments += 1

        # Keep the denormalised follower_count cache consistent with reality.
        for profile in UserProfile.objects.filter(user__username__startswith=DEMO_PREFIX):
            profile.follower_count = CreatorFollow.objects.filter(creator=profile.user).count()
            profile.save(update_fields=["follower_count"])

        self.stdout.write(
            f"  social: {follows} follows, {likes} likes, {comments} comments, {favorites} favorites"
        )

    # -- moderation / payouts ---------------------------------------------

    def _create_moderation_and_payouts(self, tracks, users, creators, rng):
        reports = 0
        public_tracks = [t for t in tracks if t.status == Track.Status.APPROVED]
        for track in rng.sample(public_tracks, k=min(len(public_tracks), 4)):
            Report.objects.create(
                reporter=rng.choice(users), target_type=Report.TargetType.TRACK, track=track,
                reason=rng.choice([Report.Reason.SPAM, Report.Reason.COPYRIGHT, Report.Reason.ABUSE]),
                details="گزارش نمونه در نسخه دمو.",
            )
            reports += 1

        Plan.objects.get_or_create(
            code="vip_monthly",
            defaults={"title": "اشتراک ماهانه VIP", "price": 99000, "duration_days": 30,
                      "description": "دانلود نامحدود و تجربه بدون محدودیت", "is_featured": True},
        )
        Plan.objects.get_or_create(
            code="vip_yearly",
            defaults={"title": "اشتراک سالانه VIP", "price": 990000, "duration_days": 365,
                      "description": "دو ماه رایگان نسبت به پلن ماهانه"},
        )

        payouts = 0
        for creator in creators[:4]:
            # Re-read: the in-memory profile predates _create_plays_and_points'
            # points recalculation, so creator.profile.points would still be 0.
            points = UserProfile.objects.get(user=creator).points
            if points > 0:
                PayoutRequest.objects.create(
                    user=creator, amount=points, points=points,
                    status=PayoutRequest.Status.PENDING,
                )
                payouts += 1

        self.stdout.write(f"  moderation: {reports} reports | payouts pending: {payouts} | plans: 2")
