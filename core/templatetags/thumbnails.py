"""Lazy, cached image thumbnails — no new model fields/migrations.

Generates a resized JPEG derivative next to the original on first request
and reuses it after that (default_storage.exists() check), on whichever
storage backend is active (local disk in dev, S3-compatible in prod — see
config/settings/prod.py's USE_S3_STORAGE). If anything goes wrong (missing
file, corrupt image, Pillow error), falls back to the original URL rather
than breaking the page.
"""

import io
import logging

from django import template
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger("casset.core")

register = template.Library()


@register.filter(name="thumbnail_url")
def thumbnail_url(image_field, size_spec: str) -> str:
    """Usage: {{ track.cover|thumbnail_url:"300x300" }}"""
    if not image_field:
        return ""

    try:
        width_str, height_str = size_spec.lower().split("x")
        width, height = int(width_str), int(height_str)
    except (ValueError, AttributeError):
        return image_field.url

    name = image_field.name
    base = name.rsplit(".", 1)[0] if "." in name else name
    derived_name = f"{base}_thumb_{width}x{height}.jpg"

    if default_storage.exists(derived_name):
        return default_storage.url(derived_name)

    try:
        from PIL import Image

        with default_storage.open(name, "rb") as src:
            img = Image.open(src)
            img.load()
            img = img.convert("RGB")
            img.thumbnail((width, height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
        default_storage.save(derived_name, ContentFile(buf.read()))
    except Exception as exc:
        logger.warning("thumbnail_url: failed to generate %s: %s", derived_name, exc)
        return image_field.url

    return default_storage.url(derived_name)
