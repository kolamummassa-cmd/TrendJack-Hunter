from django.contrib import admin
from .models import Trend


@admin.register(Trend)
class TrendAdmin(admin.ModelAdmin):
    list_display = ("name", "trend_score", "relevance_score", "source_count", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name",)
    ordering = ("-trend_score",)
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("articles",)
