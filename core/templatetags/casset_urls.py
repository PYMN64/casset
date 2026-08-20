"""URL helpers for templates."""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def abs_url(context, url: str) -> str:
    """Absolute URL for a media/static path, safe on every storage backend.

    Templates can't call `request.build_absolute_uri(url)` directly (Django
    template syntax has no way to pass an argument to a method), which is why
    the OG tags used to hand-build `{{ request.scheme }}://{{ request.get_host }}{{ ... }}`.
    That breaks as soon as USE_S3_STORAGE is on: FileField.url is then already
    an absolute https://bucket.../ URL, and prefixing it again produces
    "https://casset.ir/https://bucket..." — a dead link in every social
    preview. build_absolute_uri() leaves absolute URLs alone and only
    prefixes relative ones, which is the behavior we actually want.
    """
    if not url:
        return ""
    request = context.get("request")
    if request is None:
        return url
    return request.build_absolute_uri(url)
