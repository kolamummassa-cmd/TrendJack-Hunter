from django.core.management.base import BaseCommand

from trends.services.expiry_runner import run_trend_expiry


class Command(BaseCommand):
    help = (
        "Warns users about un-briefed trends approaching 3 days old (listing "
        "them by email so there's still time to generate a brief), then "
        "deletes those trends 1 day after the warning if they're still "
        "un-briefed. Trends that already have a brief are never touched — "
        "deleting a trend cascades and would destroy its brief too, so "
        "briefed trends are permanently exempt from this whole command. "
        "Intended to run once daily via cron/an external scheduler (no "
        "built-in scheduler yet) — see also the /trends/internal/expire-trends/ "
        "HTTP trigger for use with a free external scheduler instead of a "
        "paid Render Cron Job."
    )

    def handle(self, *args, **options):
        result = run_trend_expiry()
        self.stdout.write(
            f"Warned {result['warned_users']} user(s) about "
            f"{result['warned_trends']} expiring trend(s). "
            f"Deleted {result['deleted_trends']} trend(s) past their grace period."
        )
