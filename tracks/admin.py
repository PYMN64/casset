from django.contrib import admin
from .models import Track, Genre, Album

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ('name','slug')

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
