from django.conf import settings


def subscription_flag(request):
    return {"subscription_required": settings.SUBSCRIPTION_REQUIRED}