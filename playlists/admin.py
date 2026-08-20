from django.contrib import admin

from .models import Playlist, PlaylistItem


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    extra = 0
    autocomplete_fields = ('track',)
    readonly_fields = ('created_at',)


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'is_private', 'item_count', 'created_at')
    list_filter = ('is_private', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    autocomplete_fields = ('owner',)
    readonly_fields = ('created_at',)
    inlines = [PlaylistItemInline]

    def get_queryset(self, request):
        # Annotate once instead of a COUNT per row in item_count (N+1).
        from django.db.models import Count
        return super().get_queryset(request).select_related('owner').annotate(
            _item_count=Count('items')
        )

    @admin.display(description='Tracks', ordering='_item_count')
    def item_count(self, obj):
        return obj._item_count


@admin.register(PlaylistItem)
class PlaylistItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'playlist', 'track', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('playlist__name', 'track__title')
    autocomplete_fields = ('playlist', 'track')
    readonly_fields = ('created_at',)
