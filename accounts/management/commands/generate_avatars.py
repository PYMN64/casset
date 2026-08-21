from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw
from io import BytesIO
import random

COLORS = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
    '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A8E6CF',
]

class Command(BaseCommand):
    help = 'Generate avatars and covers for users without them'

    def handle(self, *args, **options):
        users = User.objects.filter(profile__avatar__exact='').exclude(username='admin')
        count = users.count()
        self.stdout.write(f"🎨 Generating for {count} users...\n")

        for i, user in enumerate(users, 1):
            profile = user.profile

            # Avatar
            if not profile.avatar:
                initials = (user.first_name[0] if user.first_name else user.username[0]).upper()
                if user.last_name:
                    initials += user.last_name[0].upper()

                img = Image.new('RGB', (256, 256), random.choice(COLORS))
                draw = ImageDraw.Draw(img)
                bbox = draw.textbbox((0, 0), initials)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                x = (256 - text_w) // 2
                y = (256 - text_h) // 2
                draw.text((x, y), initials, fill='white')

                f = BytesIO()
                img.save(f, 'PNG')
                f.seek(0)
                profile.avatar = ContentFile(f.read(), name=f'avatar_{user.id}.png')

            # Cover
            if not profile.cover:
                img = Image.new('RGB', (1200, 300), random.choice(COLORS))
                f = BytesIO()
                img.save(f, 'PNG')
                f.seek(0)
                profile.cover = ContentFile(f.read(), name=f'cover_{user.id}.png')

            profile.save()
            self.stdout.write(f"  [{i}/{count}] {user.username} ✓")

        self.stdout.write(self.style.SUCCESS(f'\n✅ Done! {count} users updated.'))
