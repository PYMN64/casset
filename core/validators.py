from __future__ import annotations

import imghdr

from django.core.exceptions import ValidationError


def validate_max_size(file, max_bytes: int, label: str):
    if file and getattr(file, "size", 0) > max_bytes:
        mb = max_bytes / (1024 * 1024)
        raise ValidationError(f"{label} is too large. Max size is {mb:.0f}MB")


def validate_image(file, max_bytes: int = 3 * 1024 * 1024):
    if not file:
        return
    validate_max_size(file, max_bytes, "Image")

    # imghdr works on initial bytes; reset pointer afterwards
    pos = file.file.tell() if hasattr(file, "file") else None
    try:
        head = file.read(512)
        kind = imghdr.what(None, head)
        if kind is None:
            raise ValidationError("Invalid image file")
    finally:
        try:
            file.seek(0)
        except Exception:
            pass
        if pos is not None:
            try:
                file.file.seek(pos)
            except Exception:
                pass


def validate_audio(file, max_bytes: int = 25 * 1024 * 1024):
    """Basic audio validation.

    We intentionally keep this light (no heavy decoding) but still catch obvious fakes.
    """
    if not file:
        return
    validate_max_size(file, max_bytes, "Audio")

    # Check for common headers (ID3 for MP3, RIFF for WAV, fLaC for FLAC, OggS for OGG)
    pos = file.file.tell() if hasattr(file, "file") else None
    try:
        head = file.read(4)
        if head not in (b"ID3", b"RIFF", b"fLaC", b"OggS"):
            # Some MP3s may start with frame sync instead of ID3; accept 0xFF 0xFB/0xF3/0xF2
            file.seek(0)
            head2 = file.read(2)
            if not (len(head2) == 2 and head2[0] == 0xFF and (head2[1] & 0xE0) == 0xE0):
                raise ValidationError("Invalid or unsupported audio file")
    finally:
        try:
            file.seek(0)
        except Exception:
            pass
        if pos is not None:
            try:
                file.file.seek(pos)
            except Exception:
                pass
