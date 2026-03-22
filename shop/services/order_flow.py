from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from shop.models import Order, OrderItem, PaymentAttempt
from shop.services.supplier import fulfill_item


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


@transaction.atomic
def mark_order_paid(order, provider, reference, payload=None):
    if order.payment_status == Order.PaymentStatus.PAID:
        return order

    order.status = Order.Status.FULFILLING
    order.payment_status = Order.PaymentStatus.PAID
    order.payment_provider = provider
    order.payment_reference = reference
    order.paid_at = timezone.now()
    order.save(
        update_fields=[
            "status",
            "payment_status",
            "payment_provider",
            "payment_reference",
            "paid_at",
            "updated_at",
        ]
    )

    PaymentAttempt.objects.create(
        order=order,
        provider=provider,
        reference=reference,
        status=PaymentAttempt.Status.PAID,
        raw_payload=payload or {},
    )

    for item in order.items.select_related("product").all():
        fulfill_item(item)

    order.status = Order.Status.COMPLETED
    order.fulfilled_at = timezone.now()
    order.save(update_fields=["status", "fulfilled_at", "updated_at"])
    return order
