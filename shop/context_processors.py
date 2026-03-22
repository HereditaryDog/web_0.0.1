from django.conf import settings


def site_context(request):
    return {
        "site_name": settings.SITE_NAME,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }
