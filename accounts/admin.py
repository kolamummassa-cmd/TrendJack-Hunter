from django.contrib import admin

from accounts.models import Profile, Subscription


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "payment_method", "status", "amount_kes", "current_period_end", "created_at")
    list_filter = ("plan", "payment_method", "status")
    search_fields = ("user__username", "user__email", "intasend_invoice_id", "intasend_tracking_id")
