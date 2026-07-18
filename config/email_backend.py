"""
Custom Django email backend that sends via Resend's HTTP API instead of
SMTP. This exists because SMTP (port 587) appears to be blocked or
unreliable on Render's free tier — HTTPS (what this uses) is never
blocked anywhere, sidestepping that problem entirely.
"""

import logging

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        resend.api_key = settings.RESEND_API_KEY
        sent_count = 0

        for message in email_messages:
            try:
                resend.Emails.send({
                    "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                    "to": message.to,
                    "subject": message.subject,
                    "text": message.body,
                })
                sent_count += 1
            except Exception:
                logger.exception("Failed to send email via Resend API")
                if not self.fail_silently:
                    raise

        return sent_count