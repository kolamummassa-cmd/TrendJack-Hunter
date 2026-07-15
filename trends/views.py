from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from trends.models import Trend
from briefs.models import ContentBrief
from briefs.services.openai_client import generate_brief_data, BriefGenerationError


def dashboard(request):
    """
    Main dashboard: lists all detected trends as cards, with sorting and
    filtering controls.
    """
    sort = request.GET.get("sort", "trend_score")
    status = request.GET.get("status", "all")
    min_relevance = request.GET.get("min_relevance", "")

    sort_field_map = {
        "trend_score": "-trend_score",
        "relevance_score": "-relevance_score",
        "created_at": "-created_at",
    }
    order_by = sort_field_map.get(sort, "-trend_score")

    trends = Trend.objects.all().select_related("brief")

    if status in dict(Trend.STATUS_CHOICES):
        trends = trends.filter(status=status)

    if min_relevance.isdigit():
        trends = trends.filter(relevance_score__gte=int(min_relevance))

    trends = trends.order_by(order_by)

    context = {
        "trends": trends,
        "current_sort": sort,
        "current_status": status,
        "current_min_relevance": min_relevance,
        "status_choices": Trend.STATUS_CHOICES,
        "total_count": trends.count(),
        "briefed_count": trends.filter(status=Trend.STATUS_BRIEFED).count(),
    }
    return render(request, "trends/dashboard.html", context)


def trend_detail(request, pk):
    trend = get_object_or_404(Trend, pk=pk)
    brief = getattr(trend, 'brief', None)

    has_access = False
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile is not None:
            has_access = profile.has_active_subscription()

    return render(request, "trends/trend_detail.html", {
        "trend": trend,
        "brief": brief,
        "has_access": has_access,
    })

@login_required
@require_POST
def generate_brief(request, pk):
    """
    On-demand version of the generate_briefs management command, scoped
    to a single trend. Only accessible to subscribers — mirrors the same
    relevance-threshold and generation logic the CLI command uses, so
    behavior stays consistent whether a brief is created via terminal or
    via this button.
    """
    trend = get_object_or_404(Trend, pk=pk)

    profile = getattr(request.user, "profile", None)
    if profile is None or not profile.has_active_subscription():
        messages.error(request, "An active subscription is required to generate briefs.")
        return redirect("trends:trend_detail", pk=pk)

    if trend.relevance_score < settings.MIN_RELEVANCE_SCORE_FOR_BRIEF:
        messages.error(
            request,
            f"This trend's relevance score ({trend.relevance_score}) is below "
            f"the minimum threshold for generating a brief.",
        )
        return redirect("trends:trend_detail", pk=pk)

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
        messages.error(request, f"Couldn't generate a brief right now: {exc}")
        return redirect("trends:trend_detail", pk=pk)

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

    messages.success(request, "Brief generated successfully!")
    return redirect("trends:trend_detail", pk=pk)
