from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import Article
from trends.models import Trend
from trends.services.trend_scorer import build_trend_candidates
from trends.services.relevance_scorer import score_relevance

# Only look at articles from the last N days when detecting trends — older
# articles shouldn't influence "what's hot right now".
LOOKBACK_DAYS = 14


class Command(BaseCommand):
    help = (
        "Extract topic phrases from recent articles, score them as trend "
        "candidates, score entrepreneur relevance, and save/update Trend rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookback-days",
            type=int,
            default=LOOKBACK_DAYS,
            help=f"How many days of articles to analyze (default: {LOOKBACK_DAYS}).",
        )
        parser.add_argument(
            "--skip-collect",
            action="store_true",
            help="Skip running the collectors first; only re-analyze existing articles.",
        )

    def handle(self, *args, **options):
        lookback_days = options["lookback_days"]

        if not options["skip_collect"]:
            self.stdout.write("Collecting fresh articles first (RSS, Reddit, YouTube)...\n")
            for collector in ("collect_articles", "collect_reddit", "collect_youtube"):
                try:
                    call_command(collector)
                except Exception as exc:
                    # A single collector failing (e.g. Reddit API not configured
                    # yet) shouldn't stop trend detection from running on
                    # whatever articles are already available.
                    self.stdout.write(self.style.WARNING(f"  {collector} failed: {exc}"))
            self.stdout.write("")

        cutoff = timezone.now() - timedelta(days=lookback_days)

        articles = Article.objects.filter(published_at__gte=cutoff)
        # Fall back to created_at if published_at is missing on everything
        # (e.g. a feed without dates) so the command still has data to work with.
        if not articles.exists():
            articles = Article.objects.filter(created_at__gte=cutoff)

        article_count = articles.count()
        self.stdout.write(f"Analyzing {article_count} articles from the last {lookback_days} days...\n")

        if article_count == 0:
            self.stdout.write(self.style.WARNING(
                "No articles found. Run 'python manage.py collect_articles' first."
            ))
            return

        candidates = build_trend_candidates(articles)
        self.stdout.write(f"Found {len(candidates)} trend candidates (min {2}+ sources)...\n")

        # Build a lookup of article id -> article for evidence text construction
        articles_by_id = {a.id: a for a in articles}

        created_count = 0
        updated_count = 0

        for key, data in candidates.items():
            evidence_articles = [articles_by_id[aid] for aid in data["article_ids"] if aid in articles_by_id]
            evidence_text = " ".join(f"{a.title} {a.summary}" for a in evidence_articles)

            relevance = score_relevance(data["display_name"], evidence_text)

            trend, was_created = Trend.objects.update_or_create(
                name=data["display_name"],
                defaults={
                    "trend_score": data["trend_score"],
                    "relevance_score": relevance,
                    "source_count": data["source_count"],
                },
            )
            trend.articles.set(evidence_articles)

            if was_created:
                created_count += 1
            else:
                updated_count += 1

            self.stdout.write(
                f"  - {trend.name}: trend_score={trend.trend_score}, "
                f"relevance={trend.relevance_score}, sources={trend.source_count}"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} new trends, {updated_count} updated."
        ))
