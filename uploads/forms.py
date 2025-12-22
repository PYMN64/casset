from django import forms

from core.models import PlatformSetting
from tracks.models import Album, Genre, Tag, Track


class TrackUploadForm(forms.ModelForm):
    duration_minutes = forms.IntegerField(
        min_value=0,
        required=False,
        help_text="Used to enforce upload limits.",
    )
    tags_text = forms.CharField(required=False, help_text="Comma-separated tags")

    class Meta:
        model = Track
        fields = (
            "content_type",
            "title",
            "description",
            "author_name",
            "translator_name",
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
        if user is not None:
            self.fields["album"].queryset = Album.objects.filter(creator=user)
        if self.instance and getattr(self.instance, "content_type", None) == "audiobook":
            self.initial["content_type"] = Track.ContentType.AUDIOBOOK

        setting = PlatformSetting.get_solo()
        allowed = set()
        disabled = set()

        if setting.enable_music:
            allowed.add(Track.ContentType.MUSIC)
        else:
            disabled.add(Track.ContentType.MUSIC)

        if setting.enable_podcast:
            allowed.add(Track.ContentType.PODCAST)
        else:
            disabled.add(Track.ContentType.PODCAST)

        if setting.enable_audiobook:
            allowed.add(Track.ContentType.AUDIOBOOK)
        else:
            disabled.add(Track.ContentType.AUDIOBOOK)

        if setting.enable_video:
            allowed.add(Track.ContentType.VIDEO)
        else:
            disabled.add(Track.ContentType.VIDEO)

        self.allowed_content_types = allowed
        self.disabled_content_types = disabled
        self.fields["content_type"].choices = [
            (value, "Audiobook" if value == Track.ContentType.AUDIOBOOK else label)
            for value, label in self.fields["content_type"].choices
        ]

        self.fields["genres"].queryset = Genre.objects.filter(is_active=True)
        raw_ct = (self.data.get("content_type") if hasattr(self, "data") else None) or (
            getattr(self.instance, "content_type", None)
        )
        if raw_ct:
            if raw_ct == Track.ContentType.AUDIOBOOK:
                self.fields["genres"].queryset = self.fields["genres"].queryset.filter(
                    content_type=Track.ContentType.AUDIOBOOK
                )
            else:
                self.fields["genres"].queryset = self.fields["genres"].queryset.filter(content_type=raw_ct)

    def clean(self):
        cleaned = super().clean()
        ct = cleaned.get("content_type")
        audio = cleaned.get("audio")
        video = cleaned.get("video")

        if ct in self.disabled_content_types:
            if not (self.instance and self.instance.pk and self.instance.content_type == ct):
                raise forms.ValidationError("Selected content type is disabled.")

        if ct == Track.ContentType.VIDEO:
            if not video:
                raise forms.ValidationError("Video file is required for video content.")
        else:
            if not audio:
                raise forms.ValidationError("Audio file is required for this content type.")

        album = cleaned.get("album")
        if album and album.content_type != ct:
            raise forms.ValidationError("Album content type must match track content type.")

        genres = cleaned.get("genres")
        if genres and ct:
            for genre in genres:
                if genre.content_type != ct:
                    raise forms.ValidationError("Selected genres must match track content type.")

        if ct != Track.ContentType.AUDIOBOOK:
            cleaned["author_name"] = ""
            cleaned["translator_name"] = ""

        mins = cleaned.get("duration_minutes") or 0
        cleaned["duration_seconds"] = int(mins) * 60
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.duration_seconds = int(self.cleaned_data.get("duration_seconds") or 0)
        if commit:
            obj.save()
            self.save_m2m()
            tags_raw = (self.cleaned_data.get("tags_text") or "").strip()
            if tags_raw:
                names = [t.strip() for t in tags_raw.split(",") if t.strip()]
                tag_objs = []
                for n in names[:20]:
                    slug = n.lower().replace(" ", "-")[:80]
                    tag, _ = Tag.objects.get_or_create(name=n, defaults={"slug": slug})
                    tag_objs.append(tag)
                obj.tags.set(tag_objs)
        return obj
