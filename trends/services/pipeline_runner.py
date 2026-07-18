"""
Runs the collect+detect pipeline in a background thread and emails the
triggering user once it's done. A pragmatic choice for now — a real
production deployment would use Celery instead, since a plain thread dies
silently if the dev server restarts mid-run. Good enough to remove the
"run this in the terminal yourself" requirement for now.
"""

import logging
import threading

from django.core.mail import send_mail
from django.core.management import call_command
from django.utils import timezone

from trends.models import PipelineRun, Trend

logger = logging.getLogger(__name__)


def _run_pipeline(user_email=None, username=None):
    run = PipelineRun.objects.create()
    try:
        before_count = Trend.objects.count()
        call_command("detect_trends")
        after_count = Trend.objects.count()
        new_trends = max(0, after_count - before_count)

        run.finished_at = timezone.now()
        run.trends_detected = after_count
        run.succeeded = True
        run.save(update_fields=["finished_at", "trends_detected", "succeeded"])

        if user_email:
            send_mail(
                subject="New trends are ready on Trendjack Hunter",
                message=(
                    f"Hi {username or ''},\n\n"
                    f"We've just refreshed the trend dashboard — "
                    f"{new_trends} new trend(s) detected, {after_count} total "
                    f"currently on the board.\n\n"
                    f"Head over to your dashboard to check them out.\n\n"
                    f"— Trendjack Hunter"
                ),
                from_email=None,
                recipient_list=[user_email],
            )
    except Exception:
        logger.exception("Background pipeline run failed")
        run.finished_at = timezone.now()
        run.succeeded = False
        run.save(update_fields=["finished_at", "succeeded"])


def trigger_pipeline_if_stale(user, staleness_minutes=60):
    """
    Kicks off collect+detect in a background thread ONLY if existing trend
    data is older than `staleness_minutes`. Returns True if a refresh was
    actually triggered, False if data was already fresh (so the caller can
    show an appropriate message either way).
    """
    if not PipelineRun.is_data_stale(minutes=staleness_minutes):
        return False

    thread = threading.Thread(
        target=_run_pipeline,
        kwargs={"user_email": user.email, "username": user.username},
        daemon=True,
    )
    thread.start()
    return True