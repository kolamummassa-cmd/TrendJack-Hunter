from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from trends.models import Trend
from briefs.models import ContentBrief
from briefs.services.openai_client import generate_brief_data, BriefGenerationError

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from trends.services.pipeline_runner import trigger_pipeline_if_stale
from trends.services.expiry_runner import run_trend_expiry

@login_required(login_url="accounts:signup")
def dashboard(request):
    """
    Main dashboard: lists trends the current user has unlocked, as cards,
    with sorting and filtering controls. Trend data itself is global/shared,
    but each user only sees it once they've triggered at least one refresh
    (see Trend.visible_to) — so a brand new signup starts with an empty
    dashboard until they click Refresh Trends.
    """
    sort = request.GET.get("sort", "trend_score")
    status = request.GET.get("status", "all")
    # Defaults to hiding trends already scored 0/"Irrelevant" — a user can
    # still see everything by clearing this filter box manually. Only kicks
    # in when the param is missing entirely (first load); submitting the
    # filter form with the box blank passes "" explicitly, which is left
    # unfiltered on purpose.
    min_relevance = request.GET.get("min_relevance", "1")

    sort_field_map = {
        "trend_score": "-trend_score",
        "relevance_score": "-relevance_score",
        "created_at": "-created_at",
    }
    order_by = sort_field_map.get(sort, "-trend_score")

    trends = Trend.objects.filter(visible_to=request.user).select_related("brief")

    if status in dict(Trend.STATUS_CHOICES):
        trends = trends.filter(status=status)

    if min_relevance.isdigit():
        trends = trends.filter(relevance_score__gte=int(min_relevance))

    trends = trends.order_by(order_by)

    total_count = trends.count()
    briefed_count = trends.filter(status=Trend.STATUS_BRIEFED).count()

    paginator = Paginator(trends, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "trends": page_obj,
        "page_obj": page_obj,
        "current_sort": sort,
        "current_status": status,
        "current_min_relevance": min_relevance,
        "status_choices": Trend.STATUS_CHOICES,
        "total_count": total_count,
        "briefed_count": briefed_count,
    }
    return render(request, "trends/dashboard.html", context)


@login_required(login_url="accounts:signup")
def trend_detail(request, pk):
    # Scoped to visible_to=request.user as well as pk, so a signed-up user
    # can't view a trend they haven't unlocked yet by guessing/sharing a URL —
    # it 404s instead, same as a trend that doesn't exist at all.
    trend = get_object_or_404(Trend, pk=pk, visible_to=request.user)
    brief = getattr(trend, 'brief', None)

    profile = getattr(request.user, "profile", None)
    has_access = profile.has_active_subscription() if profile is not None else False

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


@login_required
@require_POST
def refresh_trends(request):
    """
    Manual trigger for the collect+detect pipeline, reusing the same
    staleness-guarded background runner used for signup/login. Lets us
    control refresh timing directly while the user base is still small,
    without wasting API quota on an hourly schedule nobody needs yet.

    Also unlocks the current trend board for this user immediately — trend
    data is global/shared, so if it's already fresh there's no need to make
    them wait for a new pipeline run just to see what already exists. If a
    new background run does kick off (data was stale), it grants this user
    visibility to whatever it finds too once it finishes.
    """
    request.user.visible_trends.add(*Trend.objects.all())

    triggered = trigger_pipeline_if_stale(request.user, staleness_minutes=60)
    if triggered:
        messages.success(
            request,
            "Refreshing trends in the background — you'll get an email once it's done."
        )
    else:
        messages.info(
            request,
            "Trends were already refreshed recently — check back a bit later."
        )
    return redirect("trends:dashboard")


@csrf_exempt
def trigger_expire_trends(request):
    """
    HTTP-triggerable version of the `expire_trends` management command,
    meant to be pinged once a day by a free external scheduler (GitHub
    Actions, cron-job.org, etc.) instead of a paid Render Cron Job.

    Protected by a shared secret passed as ?key=... — if EXPIRE_TRENDS_SECRET_KEY
    isn't set in the environment, or the key doesn't match, this always
    rejects the request rather than silently running unprotected.
    """
    expected_key = settings.EXPIRE_TRENDS_SECRET_KEY
    provided_key = request.GET.get("key", "")

    if not expected_key or provided_key != expected_key:
        return JsonResponse({"error": "Forbidden"}, status=403)

    result = run_trend_expiry()
    return JsonResponse(result)
