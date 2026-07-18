from django.db import models
from articles.models import Article
from django.utils import timezone


class Trend(models.Model):
    """
    A detected topic/keyword that is appearing across multiple articles.

    A Trend is created/updated by the detect_trends management command,
    which extracts noun phrases from recent Articles, counts frequency,
    and links matching Articles as evidence via the `articles` M2M field.
    """

    STATUS_DETECTED = "detected"
    STATUS_BRIEFED = "briefed"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DETECTED, "Detected"),
        (STATUS_BRIEFED, "Briefed"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="The topic/keyword phrase, e.g. 'AI Agents', 'Startup Grants'.",
    )
    trend_score = models.FloatField(
        default=0.0,
        help_text=(
            "Frequency/velocity-based score. Higher means more articles "
            "are mentioning this topic, weighted toward recency."
        ),
    )
    relevance_score = models.IntegerField(
        default=0,
        help_text="0-100 score: how useful/relevant this is to founders and entrepreneurs.",
    )
    source_count = models.IntegerField(
        default=0,
        help_text="Number of distinct articles mentioning this trend.",
    )
    articles = models.ManyToManyField(
        Article,
        related_name="trends",
        blank=True,
        help_text="Articles that contributed evidence for this trend (shown as 'Sources').",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DETECTED,
        help_text="Pipeline state: detected -> briefed (has a ContentBrief) -> archived.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this trend was first detected.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time trend_score/relevance_score were recalculated.",
    )

    class Meta:
        ordering = ["-trend_score"]

    def __str__(self):
        return f"{self.name} (score={self.trend_score:.1f}, relevance={self.relevance_score})"


class PipelineRun(models.Model):
    """
    Tracks each collect+detect pipeline run, so we can tell whether trend
    data is "fresh enough" — e.g. to decide whether a new signup should
    trigger an automatic refresh — without guessing from Article/Trend
    timestamps alone.
    """
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    trends_detected = models.IntegerField(default=0)
    succeeded = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]

    @classmethod
    def is_data_stale(cls, minutes=60):
        last_success = cls.objects.filter(succeeded=True).order_by("-finished_at").first()
        if last_success is None or last_success.finished_at is None:
            return True
        return (timezone.now() - last_success.finished_at).total_seconds() > minutes * 60