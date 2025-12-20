from django.core.management.base import BaseCommand
from django.utils.text import slugify

from tracks.models import Genre


class Command(BaseCommand):
    help = "Seed core genres (Persian + English) per content type."

    CORE = {
        "music": [
            ("پاپ", "Pop", "pop"),
            ("راک", "Rock", "rock"),
            ("رپ", "Hip-Hop", "hip-hop"),
            ("الکترونیک", "Electronic", "electronic"),
            ("سنتی ایرانی", "Traditional Iranian", "traditional-iranian"),
            ("بی‌کلام", "Instrumental", "instrumental"),
            ("کلاسیک", "Classical", "classical"),
            ("جز و بلوز", "Jazz & Blues", "jazz-blues"),
            ("محلی", "Folk & Local", "folk-local"),
            ("موسیقی فیلم/بازی", "Soundtrack", "soundtrack"),
        ],
        "podcast": [
            ("تکنولوژی", "Technology", "technology"),
            ("کسب‌وکار", "Business", "business"),
            ("آموزشی", "Education", "education"),
            ("خبر و سیاست", "News & Politics", "news-politics"),
            ("فرهنگ و جامعه", "Society & Culture", "society-culture"),
            ("کمدی", "Comedy", "comedy"),
            ("داستانی", "Storytelling", "storytelling"),
            ("روانشناسی", "Psychology", "psychology"),
            ("سلامت", "Health", "health"),
            ("هنر", "Arts", "arts"),
        ],
        "book": [
            ("داستانی", "Fiction", "fiction"),
            ("غیرداستانی", "Non-fiction", "non-fiction"),
            ("توسعه فردی", "Self-help", "self-help"),
            ("کسب‌وکار", "Business", "business-book"),
            ("آموزشی", "Education", "education-book"),
            ("تاریخ", "History", "history"),
            ("زندگی‌نامه", "Biography", "biography"),
            ("روانشناسی", "Psychology", "psychology-book"),
            ("علمی", "Science", "science"),
            ("شعر", "Poetry", "poetry"),
        ],
        "video": [
            ("آموزشی", "Tutorial", "tutorial"),
            ("ولگ", "Vlog", "vlog"),
            ("سرگرمی", "Entertainment", "entertainment"),
            ("مستند", "Documentary", "documentary"),
            ("موزیک‌ویدیو", "Music Video", "music-video"),
            ("گیمینگ", "Gaming", "gaming"),
            ("خبر", "News", "news-video"),
            ("نقد و بررسی", "Review", "review"),
            ("مصاحبه", "Interview", "interview"),
            ("کلیپ کوتاه", "Shorts", "shorts"),
        ],
    }

    def handle(self, *args, **options):
        created = 0
        updated = 0
        order = 0
        for ct, items in self.CORE.items():
            order = 0
            for name_fa, name_en, slug in items:
                order += 10
                obj, was_created = Genre.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "content_type": ct,
                        "name_fa": name_fa,
                        "name_en": name_en,
                        "is_active": True,
                        "order": order,
                        "parent": None,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f"Seed complete. created={created}, updated={updated}"))
