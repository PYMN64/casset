from django.core.management.base import BaseCommand

from tracks.models import Genre


class Command(BaseCommand):
    help = "Seed core genres (Persian + English) for music content."

    CORE = [
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
    ]

    def handle(self, *args, **options):
        created = 0
        updated = 0
        order = 0
        for name_fa, name_en, slug in self.CORE:
            order += 10
            obj, was_created = Genre.objects.update_or_create(
                slug=slug,
                content_type=Genre.ContentType.MUSIC,
                defaults={
                    "name": name_fa,
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
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. created={created}, updated={updated}"
            )
        )
