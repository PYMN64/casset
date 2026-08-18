from __future__ import annotations

from django.core.exceptions import ValidationError


def validate_max_size(file, max_bytes: int, label: str):
    if file and getattr(file, "size", 0) > max_bytes:
        mb = max_bytes / (1024 * 1024)
        raise ValidationError(f"{label} is too large. Max size is {mb:.0f}MB")


def validate_image(file, max_bytes: int = 3 * 1024 * 1024):
    """Validate that *file* is really an image, via Pillow (magic bytes).

    Uses Pillow rather than the stdlib `imghdr` module: `imghdr` was
    deprecated in Python 3.11 and is removed outright in 3.13, which this
    project's own `pyproject.toml` allows (`requires-python < 3.15`).
    Pillow is already a hard dependency (used identically in
    tracks/forms.py's AlbumForm.clean_cover).
    """
    if not file:
        return
    validate_max_size(file, max_bytes, "Image")

    pos = file.file.tell() if hasattr(file, "file") else None
    try:
        from PIL import Image, UnidentifiedImageError

        try:
            file.seek(0)
            img = Image.open(file)
            img.verify()
        except (UnidentifiedImageError, OSError):
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
        # NOTE: "ID3" is a 3-byte magic (followed by version bytes), so it
        # must be compared as a prefix — `head == b"ID3"` never matches a
        # 4-byte read and would reject every real ID3v2-tagged MP3.
        has_known_header = head[:3] == b"ID3" or head in (b"RIFF", b"fLaC", b"OggS")
        if not has_known_header:
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


def validate_video(file, max_bytes: int = 300 * 1024 * 1024):
    """Basic video validation — same philosophy as validate_audio: cheap
    magic-byte checks, no real decoding, but enough to reject non-video
    files (scripts, executables, arbitrary renamed files).
    """
    if not file:
        return
    validate_max_size(file, max_bytes, "Video")

    pos = file.file.tell() if hasattr(file, "file") else None
    try:
        head = file.read(12)
        # MP4/MOV family (ISO base media container): bytes 4-8 are "ftyp".
        is_iso_media = head[4:8] == b"ftyp"
        # WebM/Matroska: EBML header.
        is_webm = head[:4] == b"\x1a\x45\xdf\xa3"
        # AVI: RIFF container with "AVI " format tag.
        is_avi = head[:4] == b"RIFF" and head[8:12] == b"AVI "
        if not (is_iso_media or is_webm or is_avi):
            raise ValidationError("Invalid or unsupported video file")
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
