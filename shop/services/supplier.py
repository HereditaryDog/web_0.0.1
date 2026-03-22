from django.conf import settings
from django.utils import timezone
import requests

from shop.models import CardCode, DeliveryRecord, Product


class FulfillmentError(Exception):
    pass


def _mock_partner_tokens(product, quantity, order_no):
    return [
        {
            "code": f"{product.slug.upper()}-{order_no[-6:]}-{index + 1:02d}",
            "mock": True,
        }
        for index in range(quantity)
    ]


def request_partner_tokens(product, quantity, order_no):
    if not settings.PARTNER_API_BASE_URL or not settings.PARTNER_API_KEY:
        return _mock_partner_tokens(product, quantity, order_no)

    response = requests.post(
        f"{settings.PARTNER_API_BASE_URL.rstrip('/')}/fulfill",
        json={
            "order_no": order_no,
            "sku": product.provider_sku,
            "quantity": quantity,
        },
        headers={"Authorization": f"Bearer {settings.PARTNER_API_KEY}"},
        timeout=settings.PARTNER_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    tokens = payload.get("tokens", [])
    if len(tokens) < quantity:
        raise FulfillmentError("合作 API 返回的卡密数量不足。")
    return tokens


def fulfill_stock_item(order_item):
    available_codes = list(
        CardCode.objects.select_for_update()
        .filter(product=order_item.product, status=CardCode.Status.AVAILABLE)[: order_item.quantity]
    )
    if len(available_codes) < order_item.quantity:
        raise FulfillmentError(f"{order_item.product.title} 库存不足。")

    for card in available_codes:
        card.status = CardCode.Status.SOLD
        card.sold_at = timezone.now()
        card.save(update_fields=["status", "sold_at", "updated_at"])
        DeliveryRecord.objects.create(
            order_item=order_item,
            source=DeliveryRecord.Source.STOCK,
            display_code=card.code,
            supplier_payload={"note": card.note},
        )


def fulfill_api_item(order_item):
    tokens = request_partner_tokens(order_item.product, order_item.quantity, order_item.order.order_no)
    for token in tokens:
        DeliveryRecord.objects.create(
            order_item=order_item,
            source=DeliveryRecord.Source.API,
            display_code=token["code"],
            supplier_payload=token,
        )


def fulfill_item(order_item):
    if order_item.product.delivery_method == Product.DeliveryMethod.STOCK_CARD:
        return fulfill_stock_item(order_item)
    return fulfill_api_item(order_item)
