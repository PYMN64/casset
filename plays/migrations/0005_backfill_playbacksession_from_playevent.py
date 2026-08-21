"""Data migration: backfill PlaybackSession from existing PlayEvent history.

Constitution: don't guess data. We only carry forward fields PlayEvent
actually has (track/user/ip/ua/timestamp/point_awarded) — anything
PlayEvent never recorded (session end time, max progress ratio) is left at
an honest default (0.0 / same-as-start), not invented. One PlaybackSession
per PlayEvent (1:1), tagged source="backfill" so it's distinguishable from
live-recorded sessions in admin/queries.
"""
from django.db import migrations

BATCH_SIZE = 1000


def backfill(apps, schema_editor):
    PlayEvent = apps.get_model("plays", "PlayEvent")
    PlaybackSession = apps.get_model("plays", "PlaybackSession")

    qs = PlayEvent.objects.all().order_by("id")
    batch = []

    def flush():
        if batch:
            PlaybackSession.objects.bulk_create(batch)
            batch.clear()

    for pe in qs.iterator(chunk_size=BATCH_SIZE):
        batch.append(PlaybackSession(
            track_id=pe.track_id,
            user_id=pe.user_id,
            play_event_id=pe.id,
            ip_hash=pe.ip_hash,
            ua_hash=pe.ua_hash or "",
            source="backfill",
            status="qualified" if pe.point_awarded else "closed",
            max_progress_ratio=1.0 if pe.point_awarded else 0.0,
            started_at=pe.created_at,
            last_seen_at=pe.created_at,
            ended_at=pe.created_at,
        ))
        if len(batch) >= BATCH_SIZE:
            flush()
    flush()


def unbackfill(apps, schema_editor):
    PlaybackSession = apps.get_model("plays", "PlaybackSession")
    PlaybackSession.objects.filter(source="backfill").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("plays", "0004_alter_pointledger_reason_playbacksession"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
