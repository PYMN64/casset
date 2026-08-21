#!/usr/bin/env python
"""
Generate avatars and profile covers for all existing users.
Fast & simple: uses initials + random colors.
"""
import os
import sys
import django
from io import BytesIO
from pathlib import Path

# Django setup
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import random

COLORS = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
    '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A8E6CF',
]

def generate_avatar(user):
    """Generate avatar with user initials."""
    initials = (user.first_name[0] if user.first_name else user.username[0]).upper()
    if user.last_name:
        initials += user.last_name[0].upper()

    # Create image
    size = 256
    img = Image.new('RGB', (size, size), random.choice(COLORS))
    draw = ImageDraw.Draw(img)

    # Draw text (use default font for simplicity)
    bbox = draw.textbbox((0, 0), initials)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2
    draw.text((x, y), initials, fill='white')

    # Save
    f = BytesIO()
    img.save(f, 'PNG')
    f.seek(0)
    return ContentFile(f.read(), name=f'avatar_{user.id}.png')

def generate_cover(user):
    """Generate cover image."""
    size = (1200, 300)
    img = Image.new('RGB', size, random.choice(COLORS))

    f = BytesIO()
    img.save(f, 'PNG')
    f.seek(0)
    return ContentFile(f.read(), name=f'cover_{user.id}.png')

def main():
    users = User.objects.filter(profile__avatar__exact='').exclude(username='admin')
    count = users.count()
    print(f"🎨 Generating avatars for {count} users...")

    for i, user in enumerate(users, 1):
        profile = user.profile

        # Avatar
        if not profile.avatar:
            profile.avatar = generate_avatar(user)
            print(f"  [{i}/{count}] {user.username}: avatar ✓")

        # Cover
        if not profile.cover:
            profile.cover = generate_cover(user)
            print(f"  [{i}/{count}] {user.username}: cover ✓")

        profile.save()

    print(f"\n✅ Done! {count} users updated.")

if __name__ == '__main__':
    main()
