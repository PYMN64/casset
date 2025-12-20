from django import forms
from tracks.models import Track, Album, Tag
from core.models import PlatformSetting


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

    def save(self, commit=True):
        obj = super().save(commit=False)
        # duration_seconds from cleaned
        obj.duration_seconds = int(self.cleaned_data.get('duration_seconds') or 0)
        if commit:
            obj.save()
            self.save_m2m()
            # tags (comma-separated)
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
