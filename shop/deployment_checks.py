import ipaddress
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from shop.services.payment import list_active_payment_gateways


LOCAL_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
}


def is_public_https_base_url(url):
    if not url:
        return False, "SITE_BASE_URL 为空。"
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    if parsed.scheme != "https":
        return False, "SITE_BASE_URL 必须是公网可访问的 HTTPS 地址，Stripe webhook 才能稳定回调。"
    if not hostname:
        return False, "SITE_BASE_URL 缺少主机名。"
    if hostname == "localhost" or hostname.endswith(".local"):
        return False, "SITE_BASE_URL 不能是 localhost 或 .local 域名，Stripe 无法从公网回调。"
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname:
            return False, "SITE_BASE_URL 主机名看起来不是公网域名。"
        return True, ""
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
        return False, "SITE_BASE_URL 当前是内网/本地地址，Stripe webhook 无法从公网访问。"
    return True, ""


def stripe_webhook_public_url():
    base_url = settings.SITE_BASE_URL.strip().rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}{reverse('shop:stripe_webhook')}"


@dataclass
class ReadinessCheck:
    key: str
    label: str
    status: str
    detail: str
    blocking: bool = False


def _database_connection_check():
    try:
        connection = connections["default"]
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return ReadinessCheck(
            key="database_connection",
            label="数据库连接",
            status="pass",
            detail=connection.settings_dict.get("ENGINE", ""),
        )
    except Exception as exc:
        return ReadinessCheck(
            key="database_connection",
            label="数据库连接",
            status="fail",
            detail=str(exc),
            blocking=True,
        )


def _migration_check():
    connection = connections["default"]
    try:
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        if plan:
            pending = [f"{migration.app_label}.{migration.name}" for migration, _ in plan]
            return ReadinessCheck(
                key="pending_migrations",
                label="迁移状态",
                status="fail",
                detail="待执行迁移：" + ", ".join(pending[:8]),
                blocking=True,
            )
        return ReadinessCheck(
            key="pending_migrations",
            label="迁移状态",
            status="pass",
            detail="所有迁移已执行",
        )
    except Exception as exc:
        return ReadinessCheck(
            key="pending_migrations",
            label="迁移状态",
            status="fail",
            detail=str(exc),
            blocking=True,
        )


def _debug_check():
    if settings.DEBUG:
        return ReadinessCheck(
            key="debug_mode",
            label="调试模式",
            status="warn",
            detail="DEBUG=True，仅适合本地或受控测试环境。",
        )
    return ReadinessCheck(
        key="debug_mode",
        label="调试模式",
        status="pass",
        detail="DEBUG=False",
    )


def _card_secret_check():
    if settings.CARD_SECRET_KEY:
        return ReadinessCheck(
            key="card_secret_key",
            label="卡密加密密钥",
            status="pass",
            detail="已配置独立 CARD_SECRET_KEY",
        )
    return ReadinessCheck(
        key="card_secret_key",
        label="卡密加密密钥",
        status="warn",
        detail="未配置独立 CARD_SECRET_KEY，当前回退到 DJANGO_SECRET_KEY。",
    )


def _site_base_url_check():
    if settings.SITE_BASE_URL:
        return ReadinessCheck(
            key="site_base_url",
            label="站点域名",
            status="pass",
            detail=settings.SITE_BASE_URL,
        )
    return ReadinessCheck(
        key="site_base_url",
        label="站点域名",
        status="warn",
        detail="SITE_BASE_URL 为空，邮件中的绝对链接将依赖当前请求域名。",
    )


def _email_check():
    backend = settings.EMAIL_BACKEND
    if backend in LOCAL_EMAIL_BACKENDS:
        return ReadinessCheck(
            key="email_backend",
            label="邮件发送",
            status="warn",
            detail=f"当前邮件后端为本地调试模式：{backend}",
        )
    if settings.EMAIL_HOST and settings.EMAIL_HOST_USER:
        return ReadinessCheck(
            key="email_backend",
            label="邮件发送",
            status="pass",
            detail=f"SMTP 已配置：{settings.EMAIL_HOST}",
        )
    return ReadinessCheck(
        key="email_backend",
        label="邮件发送",
        status="warn",
        detail="邮件后端已切到 SMTP，但关键配置仍不完整。",
    )


def _payment_gateway_check():
    gateways = list_active_payment_gateways()
    codes = [gateway.code for gateway in gateways]
    non_mock = [code for code in codes if code != "mock"]
    if non_mock:
        return ReadinessCheck(
            key="payment_gateways",
            label="支付通道",
            status="pass",
            detail="已启用：" + ", ".join(non_mock),
        )
    if "mock" in codes:
        return ReadinessCheck(
            key="payment_gateways",
            label="支付通道",
            status="warn",
            detail="当前只有 mock 支付，适合内部测试，不适合真实付款测试。",
        )
    return ReadinessCheck(
        key="payment_gateways",
        label="支付通道",
        status="fail",
        detail="没有任何可用支付通道。",
        blocking=True,
    )


def _stripe_checkout_check():
    if not settings.PAYMENT_ENABLE_STRIPE_GATEWAY:
        return ReadinessCheck(
            key="stripe_checkout",
            label="Stripe 实时支付",
            status="warn",
            detail="Stripe 支付未启用。",
        )
    if not settings.STRIPE_SECRET_KEY:
        return ReadinessCheck(
            key="stripe_checkout",
            label="Stripe 实时支付",
            status="warn",
            detail="缺少 STRIPE_SECRET_KEY，无法创建真实 Checkout Session。",
        )
    if not settings.SITE_BASE_URL:
        return ReadinessCheck(
            key="stripe_checkout",
            label="Stripe 实时支付",
            status="warn",
            detail="SITE_BASE_URL 为空，Stripe 成功/取消回跳地址不稳定。",
        )
    public_ok, public_detail = is_public_https_base_url(settings.SITE_BASE_URL)
    if not public_ok:
        return ReadinessCheck(
            key="stripe_checkout",
            label="Stripe 实时支付",
            status="warn",
            detail=f"{public_detail} 当前 webhook 地址：{stripe_webhook_public_url() or '未生成'}",
        )
    if not settings.STRIPE_WEBHOOK_SECRET:
        return ReadinessCheck(
            key="stripe_checkout",
            label="Stripe 实时支付",
            status="warn",
            detail="缺少 STRIPE_WEBHOOK_SECRET，真实支付后的 webhook 无法安全验签。",
        )
    return ReadinessCheck(
        key="stripe_checkout",
        label="Stripe 实时支付",
        status="pass",
        detail=f"currency={settings.STRIPE_CURRENCY}",
    )


def _partner_api_check():
    if settings.PARTNER_API_BASE_URL and settings.PARTNER_API_KEY:
        return ReadinessCheck(
            key="partner_api",
            label="供货接口",
            status="pass",
            detail=settings.PARTNER_API_BASE_URL,
        )
    return ReadinessCheck(
        key="partner_api",
        label="供货接口",
        status="warn",
        detail="合作 API 未配置，当前会回退到 mock 供货。",
    )


def run_readiness_checks():
    checks = [
        _database_connection_check(),
        _migration_check(),
        _debug_check(),
        _card_secret_check(),
        _site_base_url_check(),
        _email_check(),
        _payment_gateway_check(),
        _stripe_checkout_check(),
        _partner_api_check(),
    ]

    failed = [check for check in checks if check.status == "fail"]
    warnings = [check for check in checks if check.status == "warn"]
    passes = [check for check in checks if check.status == "pass"]
    return {
        "ok": not failed,
        "internal_test_ready": not failed,
        "external_user_test_ready": not failed and not warnings,
        "failed_count": len(failed),
        "warning_count": len(warnings),
        "pass_count": len(passes),
        "checks": [asdict(check) for check in checks],
    }
