from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="core:home"), name="logout"),

    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),

    path("verify-code/", views.verify_signup_code, name="verify_signup_code"),
    path("resend-code/", views.resend_signup_code, name="resend_signup_code"),

    path("subscribe/", views.subscribe, name="subscribe"),
    path("subscribe/card/", views.start_card_subscription, name="start_card_subscription"),
    path("subscribe/mpesa/", views.start_mpesa_subscription, name="start_mpesa_subscription"),
    path("subscribe/return/", views.subscribe_return, name="subscribe_return"),
    path("subscribe/status/", views.check_subscription_status, name="check_subscription_status"),

    path("account/", views.my_account, name="my_account"),
    path("account/cancel/", views.cancel_subscription, name="cancel_subscription"),
    path("account/billing/<int:sub_id>/delete/", views.delete_subscription_record, name="delete_subscription_record"),

    path("webhooks/intasend/", views.intasend_webhook, name="intasend_webhook"),]
