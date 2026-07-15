"""
Thin wrapper around the IntaSend REST API. We call the API directly with
`requests` rather than an SDK, so there's nothing extra to install and no
hidden magic — every request/response is visible right here.

Docs: https://developers.intasend.com/
"""
import requests
from django.conf import settings

SANDBOX_BASE_URL = "https://sandbox.intasend.com/api/v1"
LIVE_BASE_URL = "https://payment.intasend.com/api/v1"


def _base_url():
    return SANDBOX_BASE_URL if settings.INTASEND_TEST_MODE else LIVE_BASE_URL


def _headers():
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.INTASEND_SECRET_KEY}",
    }


def create_card_checkout(user, plan_code, amount_kes, redirect_url):
    """
    Creates a hosted IntaSend checkout link for a CARD payment.
    The user is redirected to `checkout_url` to enter their card details;
    IntaSend then redirects back to `redirect_url` and also fires a webhook.

    Returns the parsed JSON response, which includes `id` (tracking id used
    to reconcile the webhook) and `url` (where to send the user).
    """
    url = f"{_base_url()}/checkout/"
    payload = {
        "amount": str(amount_kes),
        "currency": "KES",
        "email": user.email or f"{user.username}@example.com",
        "first_name": user.first_name or user.username,
        "last_name": user.last_name or "",
        "method": "CARD-PAYMENT",
        "api_ref": f"trendjack-{plan_code}-user{user.id}",
        "redirect_url": redirect_url,
    }
    response = requests.post(url, json=payload, headers=_headers(), timeout=15)
    response.raise_for_status()
    return response.json()


def trigger_mpesa_stk_push(user, phone_number, amount_kes, plan_code):
    """
    Sends an M-Pesa STK Push prompt directly to the customer's phone.
    They approve with their M-Pesa PIN; IntaSend then fires a webhook
    telling us whether it succeeded.

    Returns the parsed JSON response, which includes `invoice` details
    used to reconcile the webhook.
    """
    url = f"{_base_url()}/payment/mpesa-stk-push/"
    payload = {
        "amount": str(amount_kes),
        "phone_number": phone_number,
        "email": user.email or f"{user.username}@example.com",
        "first_name": user.first_name or user.username,
        "last_name": user.last_name or "",
        "api_ref": f"trendjack-{plan_code}-user{user.id}",
    }
    response = requests.post(url, json=payload, headers=_headers(), timeout=15)
    response.raise_for_status()
    return response.json()


def get_payment_status(invoice_id):
    """Look up the current status of a payment/invoice by its id."""
    url = f"{_base_url()}/payment/status/{invoice_id}/"
    response = requests.get(url, headers=_headers(), timeout=15)
    response.raise_for_status()
    return response.json()
