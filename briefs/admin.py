from django.contrib import admin
from .models import ContentBrief


@admin.register(ContentBrief)
class ContentBriefAdmin(admin.ModelAdmin):
    list_display = ("trend", "urgency_score", "suggested_title", "created_at")
    list_filter = ("urgency_score", "created_at")
    search_fields = ("trend__name", "suggested_title", "suggested_hook", "content_angle")
    ordering = ("-urgency_score",)
    readonly_fields = ("created_at", "updated_at", "raw_ai_response")
