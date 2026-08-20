"""Celery tasks for tracks — currently just waveform generation.

Runs async (not in the upload request) because decoding a long podcast
episode can take a real amount of wall-clock time. CELERY_TASK_ALWAYS_EAGER
(config/settings/base.py) runs this synchronously in dev/test.
"""

import logging

from celery import shared_task

logger = logging.getLogger("casset.tracks")


@shared_task(name="tracks.generate_waveform")
def generate_waveform_task(track_id: int) -> None:
    from .audio_processing import extract_waveform_peaks
    from .models import Track

    try:
        track = Track.objects.get(pk=track_id)
    except Track.DoesNotExist:
        return
    if not track.audio:
        return

    try:
        with track.audio.open("rb") as f:
            peaks = extract_waveform_peaks(f)
    except Exception as exc:
        logger.warning("generate_waveform_task: failed for track=%s: %s", track_id, exc)
        return

    if peaks:
        Track.objects.filter(pk=track_id).update(waveform_peaks=peaks)
