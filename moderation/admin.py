from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id','target_type','reason','status','created_at','reporter','target_user','track')
    list_filter = ('target_type','reason','status','created_at')
    search_fields = ('reported_username','details','admin_note','target_user__username','reporter__username','track__title')
    autocomplete_fields = ('reporter','target_user','track','reviewed_by')
    readonly_fields = ('created_at','reviewed_at')
