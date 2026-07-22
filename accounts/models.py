from django.conf import settings
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    """
    One-to-one extension of Django's built-in User model.
    Created automatically for every new user (see signals below).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        help_text="M-Pesa phone number in format 2547XXXXXXXX",
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="True once the user has clicked the confirmation link sent to their email.",
    )

    def __str__(self):
        return f"Profile for {self.user.username}"

    def has_active_subscription(self):
        from django.conf import settings
        if not settings.SUBSCRIPTION_REQUIRED:
            return True
        sub = self.active_subscription()
        return sub is not None

    def active_subscription(self):
        return self.user.subscriptions.filter(status=Subscription.STATUS_ACTIVE).order_by("-current_period_end").first()


class Subscription(models.Model):
    """
    Represents one subscription period a user has purchased (or attempted
    to purchase). A new row is created for each renewal/attempt so we keep
    a full payment history.
    """
    PLAN_MONTHLY = "monthly"
    PLAN_YEARLY = "yearly"
    PLAN_CHOICES = [
        (PLAN_MONTHLY, "Monthly"),
        (PLAN_YEARLY, "Yearly"),
    ]

    METHOD_CARD = "card"
    METHOD_MPESA = "mpesa"
    METHOD_CHOICES = [
        (METHOD_CARD, "Card"),
        (METHOD_MPESA, "M-Pesa"),
    ]

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_FAILED = "failed"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_FAILED, "Failed"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES)
    payment_method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)

    amount_kes = models.DecimalField(max_digits=10, decimal_places=2)

    # IntaSend references — used to match up webhook callbacks to this row.
    intasend_invoice_id = models.CharField(max_length=100, blank=True, db_index=True)
    intasend_tracking_id = models.CharField(max_length=100, blank=True, db_index=True)

    current_period_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} — {self.plan}/{self.payment_method} ({self.status})"

    class Meta:
        ordering = ["-created_at"]
