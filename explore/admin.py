from django.contrib import admin

from .models import FeaturedPin


@admin.register(FeaturedPin)
class FeaturedPinAdmin(admin.ModelAdmin):
    """Editorial control over the Discover page's promoted slots.

    This is the one place staff can influence what the homepage surfaces
    without touching code or the ranking algorithm, so it belongs in the
    admin rather than being seeded by hand in the DB.
    """

    list_display = ('id', 'track', 'position', 'is_active', 'starts_at', 'ends_at', 'created_at')
    list_filter = ('is_active', 'starts_at', 'ends_at')
    list_editable = ('position', 'is_active')
    search_fields = ('track__title', 'track__creator__username')
    autocomplete_fields = ('track',)
    readonly_fields = ('created_at',)
