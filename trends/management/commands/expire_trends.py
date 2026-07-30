import logging
from collections import defaultdict

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from trends.models import Trend

logger = logging.getLogger(__name__)

WARNING_AGE_DAYS = 3
GRACE_PERIOD_DAYS = 1


class Command(BaseCommand):
    help = (
        "Warns users about un-briefed trends approaching 3 days old (listing "
        "them by email so there's still time to generate a brief), then "
        "deletes those trends 1 day after the warning if they're still "
        "un-briefed. Trends that already have a brief are never touched — "
        "deleting a trend cascades and would destroy its brief too, so "
        "briefed trends are permanently exempt from this whole command. "
        "Intended to run once daily via cron (no built-in scheduler yet)."
    )

    def handle(self, *args, **options):
        warned_users, warned_trends = self._send_warnings()
        deleted_count = self._delete_expired()

        self.stdout.write(
            f"Warned {warned_users} user(s) about {warned_trends} expiring trend(s). "
            f"Deleted {deleted_count} trend(s) past their grace period."
        )

    def _send_warnings(self):
        cutoff = timezone.now() - timezone.timedelta(days=WARNING_AGE_DAYS)
        due = list(
            Trend.objects.filter(
                created_at__lte=cutoff,
                brief__isnull=True,
                expiry_warning_sent_at__isnull=True,
            ).prefetch_related("visible_to")
        )

        by_user = defaultdict(list)
        for trend in due:
            for user in trend.visible_to.all():
                if user.email:
                    by_user[user].append(trend)

        for user, trends in by_user.items():
            trend_list = "\n".join(f"- {t.name}" for t in trends)
            try:
                send_mail(
                    subject="Trends expiring soon on Trendjack Hunter",
                    message=(
                        f"Hi {user.username},\n\n"
                        f"The following trend(s) on your dashboard haven't been "
                        f"briefed yet, and will be automatically removed in "
                        f"{GRACE_PERIOD_DAYS} day if no brief is generated for "
                        f"them first:\n\n"
                        f"{trend_list}\n\n"
                        f"Head over to your dashboard now if you'd like to "
                        f"generate a content brief for any of them before "
                        f"they're gone.\n\n"
                        f"— Trendjack Hunter"
                    ),
                    from_email=None,
                    recipient_list=[user.email],
                )
            except Exception:
                logger.exception(
                    "Failed to send trend-expiry warning email to %s", user.email
                )

        if due:
            Trend.objects.filter(pk__in=[t.pk for t in due]).update(
                expiry_warning_sent_at=timezone.now()
            )

        return len(by_user), len(due)

    def _delete_expired(self):
        grace_cutoff = timezone.now() - timezone.timedelta(days=GRACE_PERIOD_DAYS)
        expired = Trend.objects.filter(
            brief__isnull=True,
            expiry_warning_sent_at__isnull=False,
            expiry_warning_sent_at__lte=grace_cutoff,
        )
        count = expired.count()
        expired.delete()
        return count
