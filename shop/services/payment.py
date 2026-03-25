from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urljoin

import stripe
from django.conf import settings
from django.urls import reverse


@dataclass(frozen=True)
class PaymentGatewayOption:
    code: str
    label: str
    summary: str
    channel_type: str
    enabled: bool
    configured: bool
    reserved_only: bool = False


@dataclass
class CheckoutSession:
    provider: str
    reference: str
    redirect_url: str
    raw_payload: dict
    display_name: str


class PaymentGatewayError(Exception):
    pass


class PaymentGatewayUnavailable(PaymentGatewayError):
    pass


def _public_absolute_url(request, path):
    if settings.SITE_BASE_URL:
        return urljoin(f"{settings.SITE_BASE_URL}/", path.lstrip("/"))
    return request.build_absolute_uri(path)


class BasePaymentGateway(ABC):
    code = ""
    label = ""
    summary = ""
    channel_type = "redirect"
    reserved_only = False

    def is_enabled(self):
        return False

    def is_configured(self):
        return True

    def is_available(self):
        return self.is_enabled() and self.is_configured()

    def build_option(self):
        return PaymentGatewayOption(
            code=self.code,
            label=self.label,
            summary=self.summary,
            channel_type=self.channel_type,
            enabled=self.is_enabled(),
            configured=self.is_configured(),
            reserved_only=self.reserved_only,
        )

    @abstractmethod
    def create_checkout_session(self, order, request):
        raise NotImplementedError

    def verify_callback(self, **kwargs):
        return None


class MockGateway(BasePaymentGateway):
    code = "mock"
    label = "模拟支付"
    summary = "开发环境使用的本地支付网关，方便先把下单和发货流程跑通。"
    channel_type = "internal"

    def is_enabled(self):
        return settings.PAYMENT_ENABLE_MOCK_GATEWAY

    def create_checkout_session(self, order, request):
        redirect_url = request.build_absolute_uri(reverse("shop:mock_pay", args=[order.order_no]))
        return CheckoutSession(
            provider=self.code,
            reference=f"mock-{order.order_no}",
            redirect_url=redirect_url,
            raw_payload={"provider": self.code, "order_no": order.order_no},
            display_name=self.label,
        )


class StripeGateway(BasePaymentGateway):
    code = "stripe"
    label = "Stripe"
    summary = "适合国际信用卡或后续统一支付聚合使用。"
    channel_type = "redirect"

    def is_enabled(self):
        return settings.PAYMENT_ENABLE_STRIPE_GATEWAY

    def is_configured(self):
        return bool(settings.STRIPE_SECRET_KEY)

    def create_checkout_session(self, order, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        success_url = _public_absolute_url(request, reverse("shop:payment_success", args=[order.order_no]))
        cancel_url = _public_absolute_url(request, reverse("shop:payment_cancel", args=[order.order_no]))
        metadata = {
            "order_no": order.order_no,
            "order_id": str(order.id),
            "site_name": settings.SITE_NAME,
        }
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url,
                customer_email=order.contact_email or order.user.email,
                billing_address_collection="auto",
                client_reference_id=order.order_no,
                line_items=[
                    {
                        "price_data": {
                            "currency": settings.STRIPE_CURRENCY,
                            "unit_amount": int(item.unit_price * 100),
                            "product_data": {"name": item.product_title},
                        },
                        "quantity": item.quantity,
                    }
                    for item in order.items.all()
                ],
                metadata=metadata,
                payment_intent_data={"metadata": metadata},
            )
        except stripe.StripeError as exc:
            message = getattr(exc, "user_message", "") or "Stripe Checkout 创建失败，请稍后重试。"
            raise PaymentGatewayError(message) from exc
        return CheckoutSession(
            provider=self.code,
            reference=session.id,
            redirect_url=session.url,
            raw_payload=session.to_dict(),
            display_name=self.label,
        )

    def verify_callback(self, session_id="", signature_payload=b"", signature="", from_webhook=False):
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


class ReservedGateway(BasePaymentGateway):
    reserved_only = True

    def create_checkout_session(self, order, request):
        raise NotImplementedError(f"{self.label} 尚未接入。")


class AlipayGateway(ReservedGateway):
    code = "alipay"
    label = "支付宝"
    summary = "面向国内用户的主流扫码支付通道，后续可接当面付或网页支付。"
    channel_type = "qr"

    def is_enabled(self):
        return settings.PAYMENT_ENABLE_ALIPAY_GATEWAY

    def is_configured(self):
        return bool(settings.ALIPAY_APP_ID and settings.ALIPAY_GATEWAY_URL)


class WechatPayGateway(ReservedGateway):
    code = "wechat_pay"
    label = "微信支付"
    summary = "适合公众号、扫码和 H5 支付场景，后续可接商户直连。"
    channel_type = "qr"

    def is_enabled(self):
        return settings.PAYMENT_ENABLE_WECHAT_GATEWAY

    def is_configured(self):
        return bool(settings.WECHAT_APP_ID and settings.WECHAT_MCH_ID and settings.WECHAT_API_V3_KEY)


class UsdtGateway(ReservedGateway):
    code = "usdt"
    label = "USDT"
    summary = "适合数字货币收款场景，后续可接链上监听和订单确认。"
    channel_type = "crypto"

    def is_enabled(self):
        return settings.PAYMENT_ENABLE_USDT_GATEWAY

    def is_configured(self):
        return bool(settings.USDT_RECEIVE_ADDRESS)


class BankTransferGateway(ReservedGateway):
    code = "bank_transfer"
    label = "银行卡转账"
    summary = "适合线下对公或手动审核场景，后续可接凭证上传和人工确认。"
    channel_type = "manual"

    def is_enabled(self):
        return settings.PAYMENT_ENABLE_BANK_GATEWAY

    def is_configured(self):
        return bool(settings.BANK_ACCOUNT_NAME and settings.BANK_NAME and settings.BANK_ACCOUNT_NUMBER)


def _gateway_registry():
    gateways = [
        StripeGateway(),
        AlipayGateway(),
        WechatPayGateway(),
        UsdtGateway(),
        BankTransferGateway(),
        MockGateway(),
    ]
    return {gateway.code: gateway for gateway in gateways}


def list_active_payment_gateways():
    return [gateway.build_option() for gateway in _gateway_registry().values() if gateway.is_available()]


def list_reserved_payment_gateways():
    return [gateway.build_option() for gateway in _gateway_registry().values() if gateway.reserved_only]


def get_default_gateway_code():
    for code in ("stripe", "alipay", "wechat_pay", "usdt", "bank_transfer", "mock"):
        gateway = _gateway_registry().get(code)
        if gateway and gateway.is_available():
            return code
    return "mock"


def get_gateway(code=""):
    gateway_code = (code or get_default_gateway_code()).strip()
    gateway = _gateway_registry().get(gateway_code)
    if not gateway or not gateway.is_available():
        raise PaymentGatewayUnavailable(f"Payment gateway {gateway_code} is not available.")
    return gateway


def create_checkout_session(order, request, provider_code=""):
    gateway = get_gateway(provider_code)
    return gateway.create_checkout_session(order, request)


def verify_payment_callback(provider_code, **kwargs):
    gateway = _gateway_registry().get(provider_code)
    if not gateway or not gateway.is_configured():
        return None
    return gateway.verify_callback(**kwargs)
