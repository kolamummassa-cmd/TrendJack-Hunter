from django.conf import settings
from django.core.management.base import BaseCommand

from trends.models import Trend
from briefs.models import ContentBrief
from briefs.services.openai_client import generate_brief_data, BriefGenerationError


class Command(BaseCommand):
    help = (
        "Generate AI content briefs for trends that meet the minimum relevance "
        "threshold and don't already have a brief (unless --force is passed)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate briefs even for trends that already have one.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of briefs to generate this run (useful to control API cost).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        limit = options["limit"]
        min_relevance = settings.MIN_RELEVANCE_SCORE_FOR_BRIEF

        queryset = Trend.objects.filter(relevance_score__gte=min_relevance).order_by("-trend_score")
        if not force:
            queryset = queryset.filter(brief__isnull=True)

        if limit:
            queryset = queryset[:limit]

        trends = list(queryset)

        if not trends:
            self.stdout.write(self.style.WARNING(
                f"No eligible trends found (relevance >= {min_relevance}, "
                f"{'all' if force else 'without existing briefs'}). "
                "Run 'python manage.py detect_trends' first, or lower MIN_RELEVANCE_SCORE_FOR_BRIEF."
            ))
            return

        self.stdout.write(f"Generating briefs for {len(trends)} trend(s)...\n")

        success_count = 0
        failure_count = 0

        for trend in trends:
            evidence_summaries = [
                f"{a.title}: {a.summary}"[:300] for a in trend.articles.all()
            ]

            try:
                data = generate_brief_data(
                    trend_name=trend.name,
                    relevance_score=trend.relevance_score,
                    trend_score=trend.trend_score,
                    evidence_summaries=evidence_summaries,
                )
            except BriefGenerationError as exc:
                failure_count += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {trend.name}: {exc}"))
                continue

            ContentBrief.objects.update_or_create(
                trend=trend,
                defaults={
                    "why_trending": data["why_trending"],
                    "why_entrepreneurs_care": data["why_entrepreneurs_care"],
                    "content_angle": data["content_angle"],
                    "linkedin_post_idea": data["linkedin_post_idea"],
                    "instagram_reel_idea": data["instagram_reel_idea"],
                    "suggested_hook": data["suggested_hook"],
                    "suggested_title": data["suggested_title"],
                    "estimated_lifespan": data["estimated_lifespan"],
                    "video_script": data["video_script"],
                    "remix_template": data["remix_template"],
                    "urgency_score": data["urgency_score"],
                    "raw_ai_response": data["_raw"],
                },
            )
            trend.status = Trend.STATUS_BRIEFED
            trend.save(update_fields=["status"])

            success_count += 1
            self.stdout.write(f"  ✓ {trend.name}: brief generated (urgency={data['urgency_score']})")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. {success_count} briefs generated, {failure_count} failed."
        ))
