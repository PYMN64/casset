from django.contrib import admin
from .models import Track, Genre, Album

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name_fa",
        "name_en",
        "slug",
        "content_type",
        "is_active",
        "order",
        "parent",
    )
    list_filter = ("content_type", "is_active")
    search_fields = ("name", "name_fa", "name_en", "slug")
    ordering = ("content_type", "order", "name_fa")

@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('id','title','creator','content_type','created_at')
    list_filter = ('content_type','created_at')
    search_fields = ('title','creator__username')
    autocomplete_fields = ('creator',)

@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ('id','title','creator','content_type','status','play_count','like_count','created_at')
    list_filter = ('status','content_type','created_at')
    search_fields = ('title','creator__username','slug')
    autocomplete_fields = ('creator','album')
