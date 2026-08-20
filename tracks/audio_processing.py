"""Waveform peak extraction — real audio, not decoration.

Uses `soundfile` (bundles libsndfile inside the wheel) rather than pydub, so
this needs no system ffmpeg/avconv binary. libsndfile >= 1.1 decodes MP3
directly in addition to WAV/FLAC/OGG, which covers everything
core/validators.py::validate_audio accepts.
"""

import logging

import numpy as np
import soundfile as sf

logger = logging.getLogger("casset.tracks")

DEFAULT_NUM_PEAKS = 120


def extract_waveform_peaks(file_like, num_points: int = DEFAULT_NUM_PEAKS) -> list[float]:
    """Return `num_points` normalized (0-1) amplitude peaks for *file_like*.

    *file_like* must be a seekable binary file object positioned at the
    start of the audio data. Returns [] if the file can't be decoded (e.g.
    corrupt upload, unsupported codec) — callers must treat that as "no
    waveform available" and fall back to a placeholder, not an error.
    """
    try:
        data, _samplerate = sf.read(file_like, dtype="float32", always_2d=True)
    except Exception as exc:
        logger.warning("extract_waveform_peaks: could not decode audio: %s", exc)
        return []

    if data.size == 0:
        return []

    # Mono-mix across channels, then take the max absolute amplitude in each
    # of `num_points` equal-width buckets — a simple, fast peak envelope
    # that's exactly what a waveform display needs (RMS would smooth over
    # the transients that make a waveform visually readable).
    mono = np.abs(data).mean(axis=1)
    n = len(mono)
    bucket_edges = np.linspace(0, n, num_points + 1, dtype=int)

    peaks = []
    for i in range(num_points):
        start, end = bucket_edges[i], bucket_edges[i + 1]
        bucket = mono[start:end] if end > start else mono[start:start + 1]
        peaks.append(float(bucket.max()) if bucket.size else 0.0)

    peak_max = max(peaks) if peaks else 0.0
    if peak_max > 0:
        peaks = [round(p / peak_max, 4) for p in peaks]
    return peaks
