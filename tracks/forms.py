from django import forms

from core.models import PlatformSetting

from .models import Album

# Allowed image MIME types for album cover uploads.
_COVER_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
# Max cover file size: 5 MB
_COVER_MAX_BYTES = 5 * 1024 * 1024


class AlbumForm(forms.ModelForm):
    """Create / edit form for Album.

    Design decisions
    ----------------
    * ``content_type`` choices are filtered by ``PlatformSetting`` so a
      creator cannot create an album for a content type the platform has
      disabled (e.g. video before it's launched).  Same pattern used in
      ``uploads.forms.TrackUploadForm``.
    * Duplicate (creator, title, content_type) is caught here with a
      user-friendly message *before* it reaches the DB UniqueConstraint.
    * Cover upload is validated for MIME type and file size server-side.
      Client-supplied Content-Type headers are not trusted; we inspect the
      file magic bytes via Pillow so an attacker cannot bypass the check by
      renaming a file.
    * ``user`` is injected by the view — never read from POST data.
    """

    class Meta:
        model = Album
        fields = ("content_type", "title", "description", "cover", "is_public")
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 140, "autocomplete": "off"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        setting = PlatformSetting.get_solo()
        allowed = []
        if setting.enable_music:
            allowed.append(Album.ContentType.MUSIC)
        if setting.enable_podcast:
            allowed.append(Album.ContentType.PODCAST)
        if setting.enable_book or setting.enable_audiobook:
            allowed.append(Album.ContentType.AUDIOBOOK)
        if setting.enable_video:
            allowed.append(Album.ContentType.VIDEO)

        self.fields["content_type"].choices = [
            c for c in self.fields["content_type"].choices if c[0] in allowed
        ]

    # ------------------------------------------------------------------
    # Field-level validators
    # ------------------------------------------------------------------

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("عنوان الزامی است.")
        if len(title) > 140:
            raise forms.ValidationError("عنوان نمی‌تواند بیشتر از ۱۴۰ کاراکتر باشد.")
        return title

    def clean_cover(self):
        """Validate cover image: MIME type (via Pillow) + file size."""
        cover = self.cleaned_data.get("cover")
        if not cover:
            return cover

        # Size check (before reading the whole file into Pillow)
        if cover.size > _COVER_MAX_BYTES:
            raise forms.ValidationError(
                f"حجم تصویر کاور نباید بیشتر از {_COVER_MAX_BYTES // (1024 * 1024)} مگابایت باشد."
            )

        # MIME check via Pillow (reads magic bytes, ignores filename/header)
        try:
            from PIL import Image
            img = Image.open(cover)
            img.verify()  # raises on corrupt files
            cover.seek(0)  # reset after verify
            fmt = (img.format or "").lower()
            mime = f"image/{fmt}" if fmt else ""
            # webp reports 'webp', jpeg reports 'jpeg'
            if mime == "image/jpg":
                mime = "image/jpeg"
            if mime not in _COVER_ALLOWED_MIME:
                raise forms.ValidationError(
                    "فرمت تصویر باید JPEG، PNG یا WebP باشد."
                )
        except forms.ValidationError:
            raise
        except Exception:
            raise forms.ValidationError(
                "فایل آپلودشده یک تصویر معتبر نیست."
            )

        return cover

    # ------------------------------------------------------------------
    # Cross-field validation
    # ------------------------------------------------------------------

    def clean(self):
        cleaned = super().clean()

        # 1. Duplicate (creator, title, content_type) check — friendly UX
        #    before the DB UniqueConstraint fires.
        title = cleaned.get("title")
        content_type = cleaned.get("content_type")
        if self.user is not None and title and content_type:
            qs = Album.objects.filter(
                creator=self.user, title=title, content_type=content_type
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "title",
                    "شما قبلاً آلبومی با همین عنوان و همین نوع محتوا ساخته‌اید.",
                )

        # 2. content_type must be one the platform currently allows.
        #    Guards against a disabled type being submitted via a crafted POST.
        if content_type:
            setting = PlatformSetting.get_solo()
            if not setting.is_content_type_enabled(content_type):
                self.add_error(
                    "content_type",
                    "این نوع محتوا در حال حاضر در پلتفرم فعال نیست.",
                )

        return cleaned
