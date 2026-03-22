from django.core.management.base import BaseCommand

from shop.models import CardCode, HelpArticle, Product, ProductCategory, SiteAnnouncement


class Command(BaseCommand):
    help = "创建演示商品、分类、公告和库存卡密"

    def handle(self, *args, **options):
        categories = [
            {
                "name": "OpenAI Token 充值",
                "slug": "openai-token-topup",
                "summary": "合作 API 平台的 Token 充值点卡",
                "sort_order": 1,
            },
            {
                "name": "开发者点卡",
                "slug": "developer-gift-cards",
                "summary": "适合开发和测试使用的库存型点卡",
                "sort_order": 2,
            },
        ]

        for item in categories:
            category, created = ProductCategory.objects.update_or_create(slug=item["slug"], defaults=item)
            action = "创建" if created else "更新"
            self.stdout.write(self.style.SUCCESS(f"{action}分类: {category.name}"))

        samples = [
            {
                "category": ProductCategory.objects.get(slug="developer-gift-cards"),
                "title": "Open Token 5 美元点卡",
                "slug": "open-token-5usd",
                "summary": "适合轻量测试和单次充值的入门卡",
                "description": "用于合作 API 平台的充值兑换，付款后系统自动发货。",
                "face_value": "5.00",
                "token_amount": 500000,
                "price": "39.00",
                "delivery_method": Product.DeliveryMethod.STOCK_CARD,
                "badge": "热卖",
                "cover_url": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
            },
            {
                "category": ProductCategory.objects.get(slug="openai-token-topup"),
                "title": "Open Token 20 美元点卡",
                "slug": "open-token-20usd",
                "summary": "适合长期调用的高频补货方案",
                "description": "由合作 API 平台提供自动化供货，可按单自动拉取充值码。",
                "face_value": "20.00",
                "token_amount": 2200000,
                "price": "149.00",
                "delivery_method": Product.DeliveryMethod.PARTNER_API,
                "provider_sku": "api-token-20usd",
                "badge": "API 自动发货",
                "cover_url": "https://images.unsplash.com/photo-1556740749-887f6717d7e4?auto=format&fit=crop&w=1200&q=80",
            },
        ]

        for item in samples:
            product, created = Product.objects.update_or_create(slug=item["slug"], defaults=item)
            action = "创建" if created else "更新"
            self.stdout.write(self.style.SUCCESS(f"{action}商品: {product.title}"))

        announcements = [
            {
                "title": "下单后可通过订单号和邮箱快速查单",
                "body": "首页和独立查单页都支持订单号 + 邮箱查询订单状态。",
                "sort_order": 1,
                "is_pinned": True,
            },
            {
                "title": "支付层已预留 Stripe，当前默认本地模拟支付",
                "body": "开发阶段可直接走模拟支付验流程，后续切正式密钥即可。",
                "sort_order": 2,
                "is_pinned": True,
            },
        ]

        for item in announcements:
            notice, created = SiteAnnouncement.objects.update_or_create(title=item["title"], defaults=item)
            action = "创建" if created else "更新"
            self.stdout.write(self.style.SUCCESS(f"{action}公告: {notice.title}"))

        articles = [
            {
                "title": "新用户如何完成第一次下单",
                "slug": "first-order-guide",
                "section": HelpArticle.Section.GUIDE,
                "summary": "从注册、挑选商品到支付成功的一次完整流程说明。",
                "content": "1. 注册账号并登录。\n2. 进入商品详情页选择数量。\n3. 提交订单并完成支付。\n4. 支付成功后在订单详情或订单查询页查看发货内容。",
                "sort_order": 1,
                "is_featured": True,
            },
            {
                "title": "订单查询失败怎么办",
                "slug": "order-lookup-faq",
                "section": HelpArticle.Section.FAQ,
                "summary": "当订单号或邮箱查询不到结果时，可以按这几个方向排查。",
                "content": "请先确认订单号完整无误，并使用下单邮箱查询。如果仍查不到，优先检查是否支付成功，再联系站点客服人工核对。",
                "sort_order": 2,
                "is_featured": True,
            },
            {
                "title": "售后与补发说明",
                "slug": "after-sale-policy",
                "section": HelpArticle.Section.AFTERSALE,
                "summary": "关于无效卡密、未到账和补发处理的规则说明。",
                "content": "若出现未到账或卡密异常，请保留订单号、支付记录和截图。核验通过后可安排补发或售后处理。",
                "sort_order": 3,
                "is_featured": True,
            },
            {
                "title": "合作 API 对接准备项",
                "slug": "partner-api-checklist",
                "section": HelpArticle.Section.API,
                "summary": "站点准备接入真实供货 API 时需要确认的基础字段和安全项。",
                "content": "建议提前准备 SKU 映射、签名机制、失败重试策略、库存校验规则以及供应商回包日志。",
                "sort_order": 4,
                "is_featured": False,
            },
        ]

        for item in articles:
            article, created = HelpArticle.objects.update_or_create(slug=item["slug"], defaults=item)
            action = "创建" if created else "更新"
            self.stdout.write(self.style.SUCCESS(f"{action}文章: {article.title}"))

        product = Product.objects.get(slug="open-token-5usd")
        for index in range(1, 9):
            CardCode.objects.get_or_create(
                product=product,
                code=f"DEMO-TOKEN-5USD-{index:04d}",
                defaults={"note": "演示库存"},
            )

        self.stdout.write(self.style.SUCCESS("演示数据已准备完成。"))
