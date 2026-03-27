import json

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand

from shop.deployment_checks import is_public_https_base_url, stripe_webhook_public_url


class Command(BaseCommand):
    help = "检查 Stripe 测试/生产配置是否完整，并验证服务端 API 连通性。"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json", help="以 JSON 输出检查结果。")

    def handle(self, *args, **options):
        public_ok, public_detail = is_public_https_base_url(settings.SITE_BASE_URL)
        result = {
            "enabled": settings.PAYMENT_ENABLE_STRIPE_GATEWAY,
            "secret_key_configured": bool(settings.STRIPE_SECRET_KEY),
            "publishable_key_configured": bool(settings.STRIPE_PUBLISHABLE_KEY),
            "webhook_secret_configured": bool(settings.STRIPE_WEBHOOK_SECRET),
            "site_base_url": settings.SITE_BASE_URL,
            "site_base_url_public_https": public_ok,
            "site_base_url_detail": public_detail,
            "webhook_url": stripe_webhook_public_url(),
            "api_connection_ok": False,
            "api_error": "",
            "account_id": "",
            "livemode": None,
        }

        if settings.PAYMENT_ENABLE_STRIPE_GATEWAY and settings.STRIPE_SECRET_KEY:
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                account = stripe.Account.retrieve()
                result["api_connection_ok"] = True
                result["account_id"] = account.get("id", "")
                result["livemode"] = account.get("livemode")
            except Exception as exc:
                result["api_error"] = str(exc)

        result["ok"] = all(
            [
                result["enabled"],
                result["secret_key_configured"],
                result["webhook_secret_configured"],
                result["site_base_url_public_https"],
                result["api_connection_ok"],
            ]
        )

        if options["as_json"]:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            if not result["ok"]:
                raise SystemExit(1)
            return

        self.stdout.write("Stripe 配置检查")
        self.stdout.write(f"enabled={result['enabled']}")
        self.stdout.write(f"secret_key_configured={result['secret_key_configured']}")
        self.stdout.write(f"publishable_key_configured={result['publishable_key_configured']}")
        self.stdout.write(f"webhook_secret_configured={result['webhook_secret_configured']}")
        self.stdout.write(f"site_base_url={result['site_base_url'] or '(empty)'}")
        self.stdout.write(f"site_base_url_public_https={result['site_base_url_public_https']}")
        if result["site_base_url_detail"]:
            self.stdout.write(f"site_base_url_detail={result['site_base_url_detail']}")
        self.stdout.write(f"webhook_url={result['webhook_url'] or '(empty)'}")
        self.stdout.write(f"api_connection_ok={result['api_connection_ok']}")
        if result["account_id"]:
            self.stdout.write(f"account_id={result['account_id']}")
        if result["livemode"] is not None:
            self.stdout.write(f"livemode={result['livemode']}")
        if result["api_error"]:
            self.stdout.write(f"api_error={result['api_error']}")

        if not result["ok"]:
            raise SystemExit(1)
