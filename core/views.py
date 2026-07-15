from django.shortcuts import render

from trends.models import Trend
from articles.models import Article


def home(request):
    context = {
        # Real count of trends currently detected — same number shown on
        # the dashboard, not a marketing placeholder.
        "active_trends_count": Trend.objects.count(),
        # Distinct source names actually seen in collected articles
        # (e.g. "TechCrunch", "r/Entrepreneur", "YouTube - startup funding")
        # rather than a hardcoded number — grows naturally as you add
        # more RSS feeds, subreddits, or YouTube queries.
        "sources_count": Article.objects.values("source").distinct().count(),
    }
    return render(request, "core/home.html", context)