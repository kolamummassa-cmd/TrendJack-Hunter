import json
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.contrib.auth.models import User
from django.core.mail import send_mail

from accounts.forms import SignupForm, MpesaPhoneForm
from accounts.models import Subscription
from accounts.services import intasend_client

logger = logging.getLogger(__name__)

PLAN_PRICES = {
    Subscription.PLAN_MONTHLY: settings.SUBSCRIPTION_PRICE_MONTHLY_KES,
    Subscription.PLAN_YEARLY: settings.SUBSCRIPTION_PRICE_YEARLY_KES,
}

PLAN_DURATIONS = {
    Subscription.PLAN_MONTHLY: timedelta(days=30),
    Subscription.PLAN_YEARLY: timedelta(days=365),
}


import random
from django.contrib.auth.hashers import make_password
from django.utils import timezone as dj_timezone

SIGNUP_SESSION_KEY = "pending_signup"
CODE_VALID_MINUTES = 15


def _generate_and_store_code(request, username, email, password_hash):
    code = f"{random.randint(0, 999999):06d}"
    request.session[SIGNUP_SESSION_KEY] = {
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "code": code,
        "created_at": dj_timezone.now().isoformat(),
        "next": request.GET.get("next", "") or request.POST.get("next", ""),
    }
    send_mail(
        subject="Your Trendjack Hunter verification code",
        message=(
            f"Your verification code is: {code}\n\n"
            f"Enter this on the signup page to finish creating your account. "
            f"This code expires in {CODE_VALID_MINUTES} minutes.\n\n"
            f"If you didn't request this, you can safely ignore this email."
        ),
        from_email=None,
        recipient_list=[email],
    )
    print(f"[DEBUG] Verification code for {email}: {code}")  # remove once confirmed working


def signup(request):
    """
    Step 1 of signup: collect username/email/password, but DON'T create
    the User yet. Instead, stash the (already-hashed) submitted data in
    the session and email a 6-digit code. The account only actually gets
    created once that code is confirmed in verify_signup_code — so an
    unconfirmed email never results in a real account existing.
    """
    if request.user.is_authenticated:
        return redirect("trends:dashboard")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password_hash = make_password(form.cleaned_data["password1"])
            _generate_and_store_code(request, username, email, password_hash)
            return redirect("accounts:verify_signup_code")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


def verify_signup_code(request):
    """
    Step 2 of signup: user enters the code emailed to them. Only on a
    correct, non-expired code does the actual User + Profile get created.
    """
    pending = request.session.get(SIGNUP_SESSION_KEY)
    if not pending:
        messages.error(request, "Your signup session expired. Please sign up again.")
        return redirect("accounts:signup")

    if request.method == "POST":
        entered_code = request.POST.get("code", "").strip()
        created_at = timezone.datetime.fromisoformat(pending["created_at"])
        if timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at)
        expired = (timezone.now() - created_at).total_seconds() > CODE_VALID_MINUTES * 60

        if expired:
            messages.error(request, "That code has expired. Request a new one below.")
        elif entered_code != pending["code"].strip():
            messages.error(request, "Incorrect code. Please try again.")
        else:
            # Correct code — NOW we actually create the account.
            user = User.objects.create(
                username=pending["username"],
                email=pending["email"],
                password=pending["password_hash"],  # already hashed by make_password
            )
            user.profile.email_verified = True
            user.profile.save(update_fields=["email_verified"])
            del request.session[SIGNUP_SESSION_KEY]
            auth_login(request, user)
            messages.success(request, "Your account is verified and ready to go!")
            next_url = pending.get("next") or "accounts:subscribe"
            return redirect(next_url if next_url.startswith("/") else reverse_lazy(next_url))

    return render(request, "accounts/verify_signup_code.html", {"email": pending["email"]})


@require_POST
def resend_signup_code(request):
    pending = request.session.get(SIGNUP_SESSION_KEY)
    if not pending:
        messages.error(request, "Your signup session expired. Please sign up again.")
        return redirect("accounts:signup")

    _generate_and_store_code(request, pending["username"], pending["email"], pending["password_hash"])
    messages.success(request, "A new code has been sent to your email.")
    return redirect("accounts:verify_signup_code")


@login_required
def subscribe(request):
    """
    Shows current subscription status and lets the user pick a plan
    (monthly/yearly) and payment method (card/M-Pesa).
    """
    profile = request.user.profile
    active_sub = profile.active_subscription()
    mpesa_form = MpesaPhoneForm()

    return render(request, "accounts/subscribe.html", {
        "has_access": profile.has_active_subscription(),
        "active_sub": active_sub,
        "monthly_price": PLAN_PRICES[Subscription.PLAN_MONTHLY],
        "yearly_price": PLAN_PRICES[Subscription.PLAN_YEARLY],
        "mpesa_form": mpesa_form,

    })


@login_required
@require_POST
def start_card_subscription(request):


    plan = request.POST.get("plan")
    if plan not in PLAN_PRICES:
        messages.error(request, "Please choose a valid plan.")
        return redirect("accounts:subscribe")

    amount = PLAN_PRICES[plan]
    sub = Subscription.objects.create(
        user=request.user,
        plan=plan,
        payment_method=Subscription.METHOD_CARD,
        status=Subscription.STATUS_PENDING,
        amount_kes=amount,
    )

    redirect_url = request.build_absolute_uri(reverse("accounts:subscribe_return"))

    try:
        resp = intasend_client.create_card_checkout(
            user=request.user,
            plan_code=plan,
            amount_kes=amount,
            redirect_url=redirect_url,
        )
    except Exception:
        logger.exception("IntaSend card checkout creation failed")
        sub.status = Subscription.STATUS_FAILED
        sub.save(update_fields=["status"])
        messages.error(request, "Couldn't start card checkout. Please try again.")
        return redirect("accounts:subscribe")

    sub.intasend_tracking_id = resp.get("id", "")
    sub.save(update_fields=["intasend_tracking_id"])

    checkout_url = resp.get("url")
    if not checkout_url:
        messages.error(request, "IntaSend didn't return a checkout link. Please try again.")
        return redirect("accounts:subscribe")

    return redirect(checkout_url)


@login_required
@require_POST
def start_mpesa_subscription(request):


    plan = request.POST.get("plan")
    if plan not in PLAN_PRICES:
        messages.error(request, "Please choose a valid plan.")
        return redirect("accounts:subscribe")

    form = MpesaPhoneForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter a valid M-Pesa phone number.")
        return redirect("accounts:subscribe")

    phone_number = form.cleaned_data["phone_number"]
    amount = PLAN_PRICES[plan]

    sub = Subscription.objects.create(
        user=request.user,
        plan=plan,
        payment_method=Subscription.METHOD_MPESA,
        status=Subscription.STATUS_PENDING,
        amount_kes=amount,
    )

    try:
        resp = intasend_client.trigger_mpesa_stk_push(
            user=request.user,
            phone_number=phone_number,
            amount_kes=amount,
            plan_code=plan,
        )
    except Exception:
        logger.exception("IntaSend M-Pesa STK push failed")
        sub.status = Subscription.STATUS_FAILED
        sub.save(update_fields=["status"])
        messages.error(request, "Couldn't send the M-Pesa prompt. Please try again.")
        return redirect("accounts:subscribe")

    invoice = resp.get("invoice", {})
    sub.intasend_invoice_id = invoice.get("invoice_id", "")
    sub.save(update_fields=["intasend_invoice_id"])

    request.user.profile.phone_number = phone_number
    request.user.profile.save(update_fields=["phone_number"])

    messages.success(
        request,
        "Check your phone — enter your M-Pesa PIN to complete the payment. "
        "Your subscription will activate automatically once payment is confirmed.",
    )
    return redirect("accounts:subscribe")


@login_required
def subscribe_return(request):
    """
    Card payments redirect here after checkout. The webhook is the source
    of truth for actually activating the subscription (redirects can be
    closed/interrupted), so this page just shows a friendly status message.
    """
    profile = request.user.profile
    if profile.has_active_subscription():
        messages.success(request, "Payment confirmed — your subscription is now active!")
    else:
        messages.info(
            request,
            "We're waiting for payment confirmation. This usually takes a few seconds — "
            "refresh in a moment if your subscription isn't active yet.",
        )
    return redirect("accounts:subscribe")


def _activate_subscription(sub):
    plan_duration = PLAN_DURATIONS[sub.plan]
    sub.status = Subscription.STATUS_ACTIVE
    sub.current_period_end = timezone.now() + plan_duration
    sub.save(update_fields=["status", "current_period_end"])


@csrf_exempt
@require_POST
def intasend_webhook(request):
    """
    IntaSend calls this URL when a payment's status changes. IntaSend's
    webhooks include a `challenge` field that must match the secret string
    configured in your IntaSend dashboard (Settings > Webhooks) — this is
    how we verify the request actually came from IntaSend.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    if payload.get("challenge") != settings.INTASEND_WEBHOOK_CHALLENGE:
        logger.warning("IntaSend webhook rejected: challenge mismatch")
        return HttpResponse(status=403)

    state = payload.get("state") or payload.get("status")
    tracking_id = payload.get("id") or payload.get("tracking_id", "")
    invoice_id = payload.get("invoice_id", "")

    sub = None
    if tracking_id:
        sub = Subscription.objects.filter(intasend_tracking_id=tracking_id).order_by("-created_at").first()
    if sub is None and invoice_id:
        sub = Subscription.objects.filter(intasend_invoice_id=invoice_id).order_by("-created_at").first()

    if sub is None:
        logger.warning("IntaSend webhook: no matching subscription for payload %s", payload)
        return HttpResponse(status=200)  # acknowledge receipt anyway

    if state in ("COMPLETE", "COMPLETED", "SUCCESS"):
        _activate_subscription(sub)
    elif state in ("FAILED", "CANCELLED"):
        sub.status = Subscription.STATUS_FAILED
        sub.save(update_fields=["status"])

    return HttpResponse(status=200)


@login_required
@require_POST
def check_subscription_status(request):
    """
    Small polling endpoint the subscribe page can call while waiting for an
    M-Pesa STK push to be confirmed, so the UI can update without a full
    page reload.
    """
    return JsonResponse({"has_access": request.user.profile.has_active_subscription()})

@login_required
def my_account(request):
    """
    Self-service account page: profile info, current subscription status,
    and full billing history. This is distinct from Django's /admin/,
    which stays reserved for staff only.
    """
    profile = request.user.profile
    active_sub = profile.active_subscription()
    billing_history = request.user.subscriptions.all()  # already ordered -created_at via model Meta

    return render(request, "accounts/my_account.html", {
        "profile": profile,
        "has_access": profile.has_active_subscription(),
        "active_sub": active_sub,
        "billing_history": billing_history,
    })


@login_required
@require_POST
def cancel_subscription(request):
    """
    Ends the user's current active subscription immediately. Since this
    platform doesn't auto-charge recurring payments (each renewal is a
    deliberate action — card checkout or M-Pesa STK push — not an
    automatic recurring billing subscription), "cancelling" simply means
    marking the current active period as cancelled rather than calling
    an external recurring-billing API.
    """
    profile = request.user.profile
    active_sub = profile.active_subscription()
    if active_sub:
        active_sub.status = Subscription.STATUS_CANCELLED
        active_sub.save(update_fields=["status"])
        messages.success(request, "Your subscription has been cancelled.")
    else:
        messages.info(request, "You don't have an active subscription to cancel.")
    return redirect("accounts:my_account")


@login_required
@require_POST
def delete_subscription_record(request, sub_id):
    """
    Deletes a single billing-history row. Blocked for the subscription
    currently granting active access, so a user can't accidentally
    remove the record proving their current paid access — only
    historical (expired/failed/cancelled/old) rows can be cleared.
    """
    sub = get_object_or_404(Subscription, id=sub_id, user=request.user)
    profile = request.user.profile
    active_sub = profile.active_subscription()

    if active_sub and sub.id == active_sub.id:
        messages.error(request, "You can't delete your currently active subscription record.")
    else:
        sub.delete()
        messages.success(request, "Billing history entry deleted.")

    return redirect("accounts:my_account")