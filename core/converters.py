"""Custom URL path converters."""


class UnicodeSlugConverter:
    """A slug converter that accepts non-ASCII (e.g. Persian) slugs.

    Django's built-in `slug` converter is ASCII-only (`[-a-zA-Z0-9_]+`), but
    this project generates slugs with `slugify(..., allow_unicode=True)`
    (tracks/models.py) — so a track titled "رویای نیمه‌شب" gets the slug
    "رویای-نیمهشب" and its detail page was unreachable: the URL simply did
    not match, and `{% url 'track_detail' %}` raised NoReverseMatch.

    On a Persian-language platform that meant essentially every real track
    was un-linkable — the bug was invisible only because seeded/demo data
    and tests had used ASCII titles.

    `\\w` is Unicode-aware in Python 3, so `[-\\w]+` covers Persian, Arabic
    and Latin alike while still excluding "/" (so it can't swallow path
    separators).
    """

    regex = r"[-\w]+"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value
