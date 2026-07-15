from django.contrib import admin
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at", "created_at")
    list_filter = ("source", "published_at", "created_at")
    search_fields = ("title", "summary", "matched_keywords", "url")
    ordering = ("-published_at",)
    readonly_fields = ("created_at",)
    date_hierarchy = "published_at"
