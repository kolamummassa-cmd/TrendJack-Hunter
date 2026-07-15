from django.db import models


class Article(models.Model):
    """
    A single item pulled in from a monitored source: an RSS article, a
    YouTube video, or a Reddit post. Despite the name, this model is the
    generic "raw evidence" row for the whole monitoring layer — trend
    detection reads across all of these regardless of source_type.

    This is the raw evidence layer of the pipeline. Nothing here is AI
    generated — it's just what the source published. Trend detection later
    reads across many Articles to find recurring topics.
    """

    SOURCE_RSS = "rss"
    SOURCE_YOUTUBE = "youtube"
    SOURCE_REDDIT = "reddit"
    SOURCE_TYPE_CHOICES = [
        (SOURCE_RSS, "RSS / News"),
        (SOURCE_YOUTUBE, "YouTube"),
        (SOURCE_REDDIT, "Reddit"),
    ]

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default=SOURCE_RSS,
        help_text="Which monitoring layer this item came from.",
    )
    title = models.CharField(
        max_length=500,
        help_text="Article headline, as published by the source.",
    )
    source = models.CharField(
        max_length=150,
        help_text="Human-readable source name, e.g. 'TechCrunch', 'Google News'.",
    )
    url = models.URLField(
        max_length=1000,
        unique=True,
        help_text="Canonical article URL. Unique — used as the dedupe key on ingestion.",
    )
    summary = models.TextField(
        blank=True,
        help_text="RSS description/snippet. Short summary, not full article text.",
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the source published this article (from RSS feed metadata).",
    )
    raw_content = models.TextField(
        blank=True,
        help_text="Optional fuller text content, if the feed provides more than a snippet.",
    )
    matched_keywords = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            "Comma-separated keywords/phrases this article was matched to during "
            "trend detection. Filled in by the detect_trends command, not on ingestion."
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this article was ingested into our database (not published date).",
    )

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return f"{self.title[:60]} ({self.source})"
