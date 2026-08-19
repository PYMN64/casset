from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import PhoneOTP, UserProfile

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fk_name = 'user'
    extra = 0


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user','display_name','phone_number','onboarding_complete','creator_enabled','creator_status','points','is_vip','vip_until','follower_count')
    list_filter = ('creator_enabled','creator_status','is_vip')
    search_fields = ('user__username','display_name','bio')
    autocomplete_fields = ('user',)


try:
    # Django registers the default User model in admin by default.
    # We replace it to show the profile inline.
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "created_at", "expires_at", "is_used", "attempts", "ip_address")
    list_filter = ("is_used",)
    search_fields = ("phone_number", "ip_address")
    readonly_fields = (
        "phone_number",
        "code_hash",
        "created_at",
        "expires_at",
        "is_used",
        "attempts",
        "last_sent_at",
        "ip_address",
        "user_agent",
    )
