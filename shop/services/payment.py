from dataclasses import dataclass

import stripe
from django.conf import settings
from django.urls import reverse


@dataclass
class CheckoutSession:
    provider: str
    reference: str
    redirect_url: str
    raw_payload: dict


def create_checkout_session(order, request):
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        success_url = request.build_absolute_uri(reverse("shop:payment_success", args=[order.order_no]))
        cancel_url = request.build_absolute_uri(reverse("shop:payment_cancel", args=[order.order_no]))
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=cancel_url,
            line_items=[
                {
                    "price_data": {
                        "currency": "hkd",
                        "unit_amount": int(item.unit_price * 100),
                        "product_data": {"name": item.product_title},
                    },
                    "quantity": item.quantity,
                }
                for item in order.items.all()
            ],
            metadata={"order_no": order.order_no},
        )
        return CheckoutSession(
            provider="stripe",
            reference=session.id,
            redirect_url=session.url,
            raw_payload=session.to_dict(),
        )

    redirect_url = request.build_absolute_uri(reverse("shop:mock_pay", args=[order.order_no]))
    return CheckoutSession(
        provider="mock",
        reference=f"mock-{order.order_no}",
        redirect_url=redirect_url,
        raw_payload={"provider": "mock", "order_no": order.order_no},
    )


def verify_stripe_checkout(session_id="", signature_payload=b"", signature="", from_webhook=False):
    if not settings.STRIPE_SECRET_KEY:
        return None

    stripe.api_key = settings.STRIPE_SECRET_KEY
    if from_webhook:
        try:
            event = stripe.Webhook.construct_event(
                payload=signature_payload,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
            return event.to_dict()
        except Exception:
            return None

    try:
        return stripe.checkout.Session.retrieve(session_id).to_dict()
    except Exception:
        return None
