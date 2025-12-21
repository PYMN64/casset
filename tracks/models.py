from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Genre(models.Model):
    class ContentType(models.TextChoices):
        MUSIC = "music", "Music"
        PODCAST = "podcast", "Podcast"
        AUDIOBOOK = "audiobook", "Audiobook"
        VIDEO = "video", "Video"

    name = models.CharField(max_length=64, blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    content_type = models.CharField(
        max_length=16, choices=ContentType.choices, default=ContentType.MUSIC
    )
    name_fa = models.CharField(max_length=64, blank=True)
    name_en = models.CharField(max_length=64, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["content_type", "order", "name_fa"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_name = self.name or self.name_fa or self.name_en or "genre"
            self.slug = slugify(base_name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name_fa or self.name or self.name_en or self.slug


class Tag(models.Model):
    """Lightweight tags used for discovery and filtering.

    Kept separate from Genre to allow both:
    - Genre: curated taxonomy
    - Tag: creator/community labels
    """

    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



class Album(models.Model):
    class ContentType(models.TextChoices):
        MUSIC = 'music', 'Music'
        PODCAST = 'podcast', 'Podcast'
        AUDIOBOOK = 'audiobook', 'Audiobook'
        VIDEO = 'video', 'Video'

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='albums')
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to='album_covers/', blank=True, null=True)
    content_type = models.CharField(max_length=16, choices=ContentType.choices, default=ContentType.MUSIC)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['creator','title','content_type'], name='uniq_album_creator_title_type')]

    def __str__(self):
        return f"{self.title} ({self.content_type})"

class Track(models.Model):
    class ContentType(models.TextChoices):
        MUSIC = 'music', 'Music'
        PODCAST = 'podcast', 'Podcast'
        AUDIOBOOK = 'audiobook', 'Audiobook'
        VIDEO = 'video', 'Video'

    class Status(models.TextChoices):
        # New lifecycle (keep legacy PENDING for backward compat)
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        TAKEDOWN = "takedown", "Takedown"
        BLOCKED = "blocked", "Blocked"
        # Legacy value used by older DBs/flows
        PENDING = "pending", "Pending (legacy)"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        UNLISTED = "unlisted", "Unlisted"
        PRIVATE = "private", "Private"

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracks"
    )

    content_type = models.CharField(max_length=16, choices=ContentType.choices, default=ContentType.MUSIC)
    album = models.ForeignKey('tracks.Album', on_delete=models.SET_NULL, null=True, blank=True, related_name='tracks')

    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=170, unique=True)

    description = models.TextField(blank=True)

    # Extra metadata (MVP+)
    language = models.CharField(max_length=16, blank=True)
    explicit = models.BooleanField(default=False)
    visibility = models.CharField(max_length=12, choices=Visibility.choices, default=Visibility.PRIVATE)

    cover = models.ImageField(upload_to="covers/", blank=True, null=True)
    audio = models.FileField(upload_to="audio/", blank=True, null=True)
    video = models.FileField(upload_to="video/", blank=True, null=True)

    duration_seconds = models.PositiveIntegerField(default=0)
    allow_comments = models.BooleanField(default=True)

    def cover_src(self):
        return self.cover.url if self.cover else ""

    def audio_src(self):
        return self.audio.url if self.audio else ""


    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    reject_reason = models.CharField(max_length=240, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    play_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)

    genres = models.ManyToManyField(Genre, blank=True, related_name="tracks")
    tags = models.ManyToManyField(Tag, blank=True, related_name="tracks")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=True)[:150] or "track"
            slug = base
            i = 2
            while Track.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
