from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from tracks.models import Track, Album, Tag
from core.models import PlatformSetting
from core.validators import validate_audio, validate_image, validate_video

# Podcast episodes and audiobook chapters run long — 25MB (core.validators'
# generic default) is too tight for this product. Cap generously instead of
# leaving audio completely unvalidated.
_TRACK_AUDIO_MAX_BYTES = 150 * 1024 * 1024
_TRACK_COVER_MAX_BYTES = 5 * 1024 * 1024


class TrackUploadForm(forms.ModelForm):
    duration_minutes = forms.IntegerField(min_value=0, required=False, help_text='برای محدودیت 180 دقیقه (تقریبی)')
    tags_text = forms.CharField(required=False, help_text="تگ‌ها را با ویرگول جدا کنید")

    class Meta:
        model = Track
        fields = (
            "content_type",
            "title",
            "description",
            "language",
            "explicit",
            "visibility",
            "cover",
            "audio",
            "video",
            "album",
            "genres",
            "allow_comments",
        )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # limit album choices to creator
        if user is not None:
            self.fields['album'].queryset = Album.objects.filter(creator=user)
        # disable unavailable content types based on platform setting
        s = PlatformSetting.get_solo()
        allowed = []
        if s.enable_music:
            allowed.append(Track.ContentType.MUSIC)
        if s.enable_podcast:
            allowed.append(Track.ContentType.PODCAST)
        # audiobook maps to "book" in UX; keep internal choice as audiobook for now
        if s.enable_book or s.enable_audiobook:
            allowed.append(Track.ContentType.AUDIOBOOK)
        if s.enable_video:
            allowed.append(Track.ContentType.VIDEO)

        self.fields["content_type"].choices = [
            c for c in self.fields["content_type"].choices if c[0] in allowed
        ]

    # ------------------------------------------------------------------
    # Field-level validators — server-side, magic-byte based. A client
    # Content-Type header or a renamed extension is never trusted (same
    # rule already applied to AlbumForm.clean_cover in tracks/forms.py).
    # ------------------------------------------------------------------

    def clean_cover(self):
        cover = self.cleaned_data.get("cover")
        try:
            validate_image(cover, max_bytes=_TRACK_COVER_MAX_BYTES)
        except DjangoValidationError:
            raise forms.ValidationError(
                f"کاور باید یک تصویر معتبر و حداکثر {_TRACK_COVER_MAX_BYTES // (1024 * 1024)} مگابایت باشد."
            )
        return cover

    def clean_audio(self):
        audio = self.cleaned_data.get("audio")
        try:
            validate_audio(audio, max_bytes=_TRACK_AUDIO_MAX_BYTES)
        except DjangoValidationError:
            raise forms.ValidationError(
                f"فایل صوتی باید معتبر و حداکثر {_TRACK_AUDIO_MAX_BYTES // (1024 * 1024)} مگابایت باشد."
            )
        return audio

    def clean_video(self):
        video = self.cleaned_data.get("video")
        try:
            validate_video(video)
        except DjangoValidationError:
            raise forms.ValidationError("فایل ویدیو معتبر نیست یا حجم آن بیش از حد مجاز است.")
        return video

    def clean(self):
        cleaned = super().clean()
        ct = cleaned.get('content_type')
        audio = cleaned.get('audio')
        video = cleaned.get('video')

        if ct == Track.ContentType.VIDEO:
            if not video:
                raise forms.ValidationError('برای ویدیو، فایل ویدیو الزامی است.')
        else:
            if not audio:
                raise forms.ValidationError('برای این نوع محتوا، فایل صوتی الزامی است.')

        # album content type must match
        album = cleaned.get('album')
        if album and album.content_type != ct:
            raise forms.ValidationError('نوع آلبوم با نوع محتوا یکی نیست.')

        # duration
        mins = cleaned.get('duration_minutes') or 0
        cleaned['duration_seconds'] = int(mins) * 60
        return cleaned

    def _apply_tags_text(self, obj):
        """Parse `tags_text` (comma-separated) into real Tag objects.

        Split out of save() because every caller in this codebase
        (upload_track, edit_track) uses the commit=False + form.save_m2m()
        pattern — this must run whenever save_m2m() runs, not only on the
        commit=True path, or tags_text silently does nothing.
        """
        tags_raw = (self.cleaned_data.get("tags_text") or "").strip()
        if not tags_raw:
            return
        names = [t.strip() for t in tags_raw.split(",") if t.strip()]
        tag_objs = []
        for n in names[:20]:
            slug = n.lower().replace(" ", "-")[:80]
            tag, _ = Tag.objects.get_or_create(name=n, defaults={"slug": slug})
            tag_objs.append(tag)
        obj.tags.set(tag_objs)

    def save(self, commit=True):
        obj = super().save(commit=False)
        # duration_seconds from cleaned
        obj.duration_seconds = int(self.cleaned_data.get('duration_seconds') or 0)
        if commit:
            obj.save()
            self.save_m2m()
            self._apply_tags_text(obj)
        else:
            # Standard Django recipe for custom processing on a deferred
            # save: wrap save_m2m so whichever view later calls it (with
            # commit=False, every current caller does) also applies tags.
            _original_save_m2m = self.save_m2m

            def save_m2m():
                _original_save_m2m()
                self._apply_tags_text(obj)

            self.save_m2m = save_m2m
        return obj
