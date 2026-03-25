import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from shop.models import Order, OrderItem, PaymentAttempt
from shop.services.supplier import FulfillmentError, fulfill_item

logger = logging.getLogger(__name__)


@transaction.atomic
def create_single_item_order(user, product, quantity):
    order = Order.objects.create(
        user=user,
        contact_email=user.email,
        payment_provider="pending",
        subtotal=Decimal("0.00"),
        total_amount=Decimal("0.00"),
    )
    unit_price = product.price
    line_total = unit_price * quantity
    OrderItem.objects.create(
        order=order,
        product=product,
        product_title=product.title,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
    )
    order.sync_totals()
    order.save(update_fields=["subtotal", "total_amount", "updated_at"])
    return order


def _upsert_payment_attempt(order, provider, reference, *, status, payload=None, checkout_url=""):
    attempt, _ = PaymentAttempt.objects.update_or_create(
        order=order,
        provider=provider,
        reference=reference,
        defaults={
            "status": status,
            "checkout_url": checkout_url,
            "raw_payload": payload or {},
        },
    )
    return attempt


def mark_order_checkout_created(order, provider, reference, checkout_url, payload=None):
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.payment_status == Order.PaymentStatus.PAID:
            return locked_order

        locked_order.status = Order.Status.PENDING_PAYMENT
        locked_order.payment_status = Order.PaymentStatus.CHECKOUT_CREATED
        locked_order.payment_provider = provider
        locked_order.payment_reference = reference
        locked_order.checkout_url = checkout_url
        locked_order.save(
            update_fields=[
                "status",
                "payment_status",
                "payment_provider",
                "payment_reference",
                "checkout_url",
                "updated_at",
            ]
        )
        _upsert_payment_attempt(
            locked_order,
            provider,
            reference,
            status=PaymentAttempt.Status.CREATED,
            payload=payload,
            checkout_url=checkout_url,
        )
        return locked_order


def mark_order_payment_failed(order, provider, reference, payload=None):
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.payment_status == Order.PaymentStatus.PAID:
            return locked_order

        locked_order.status = Order.Status.PENDING_PAYMENT
        locked_order.payment_status = Order.PaymentStatus.UNPAID
        locked_order.payment_provider = provider
        locked_order.payment_reference = reference
        locked_order.checkout_url = ""
        locked_order.save(
            update_fields=[
                "status",
                "payment_status",
                "payment_provider",
                "payment_reference",
                "checkout_url",
                "updated_at",
            ]
        )
        _upsert_payment_attempt(
            locked_order,
            provider,
            reference,
            status=PaymentAttempt.Status.FAILED,
            payload=payload,
        )
        return locked_order


def _mark_payment_received(order_id, provider, reference, payload):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.payment_status == Order.PaymentStatus.PAID:
            return order

        order.status = Order.Status.FULFILLING
        order.payment_status = Order.PaymentStatus.PAID
        order.payment_provider = provider
        order.payment_reference = reference
        order.checkout_url = ""
        order.paid_at = timezone.now()
        order.save(
            update_fields=[
                "status",
                "payment_status",
                "payment_provider",
                "payment_reference",
                "checkout_url",
                "paid_at",
                "updated_at",
            ]
        )

        _upsert_payment_attempt(
            order,
            provider,
            reference,
            status=PaymentAttempt.Status.PAID,
            payload=payload,
        )
        return order


def _fulfill_paid_order(order_id):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status == Order.Status.COMPLETED:
            return order
        if order.payment_status != Order.PaymentStatus.PAID:
            raise ValueError("Only paid orders can be fulfilled.")

        if order.status != Order.Status.FULFILLING:
            order.status = Order.Status.FULFILLING
            order.save(update_fields=["status", "updated_at"])

        for item in order.items.select_related("product").all():
            fulfill_item(item)

        order.status = Order.Status.COMPLETED
        order.fulfilled_at = timezone.now()
        order.save(update_fields=["status", "fulfilled_at", "updated_at"])
        return order


def _mark_fulfillment_failed(order_id):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        order.status = Order.Status.FAILED
        order.save(update_fields=["status", "updated_at"])
        return order


def mark_order_paid(order, provider, reference, payload=None):
    paid_order = _mark_payment_received(order.pk, provider, reference, payload)
    if paid_order.status in {Order.Status.COMPLETED, Order.Status.FAILED}:
        return paid_order

    try:
        return _fulfill_paid_order(paid_order.pk)
    except FulfillmentError as exc:
        logger.warning("Fulfillment failed for paid order %s: %s", paid_order.order_no, exc)
        return _mark_fulfillment_failed(paid_order.pk)
    except Exception:
        logger.exception("Failed to fulfill paid order %s", paid_order.order_no)
        return _mark_fulfillment_failed(paid_order.pk)


def retry_order_fulfillment(order):
    if order.payment_status != Order.PaymentStatus.PAID:
        raise ValueError("Only paid orders can retry fulfillment.")

    try:
        return _fulfill_paid_order(order.pk)
    except FulfillmentError as exc:
        logger.warning("Fulfillment retry failed for paid order %s: %s", order.order_no, exc)
        return _mark_fulfillment_failed(order.pk)
    except Exception:
        logger.exception("Unexpected fulfillment retry failure for paid order %s", order.order_no)
        return _mark_fulfillment_failed(order.pk)
