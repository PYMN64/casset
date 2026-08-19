from django.contrib import admin

from .models import Invoice, PayoutRequest, Plan, Transaction


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "code", "price", "duration_days", "is_active", "is_featured", "sort_order")
    list_editable = ("price", "is_active", "is_featured", "sort_order")
    list_filter = ("is_active", "is_featured")
    search_fields = ("title", "code", "slug")
    prepopulated_fields = {"slug": ("code",)}


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ("kind", "status", "raw_payload", "created_at")
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "amount", "status", "created_at", "paid_at", "valid_until")
    list_filter = ("status", "plan")
    search_fields = ("user__username", "provider_ref")
    autocomplete_fields = ("user", "plan")
    inlines = [TransactionInline]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice", "kind", "status", "created_at")
    list_filter = ("kind", "status")


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "status", "created_at", "paid_at")
    list_filter = ("status",)
    search_fields = ("user__username",)
    autocomplete_fields = ("user",)
