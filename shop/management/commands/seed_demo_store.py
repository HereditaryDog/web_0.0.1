from django.core.management.base import BaseCommand

from shop.models import CardCode, HelpArticle, Product, ProductCategory, SiteAnnouncement


class Command(BaseCommand):
    help = "创建演示商品、分类、公告和库存卡密"

    def handle(self, *args, **options):
        categories = [
            {
                "name": "美元充值卡",
                "slug": "openai-token-topup",
                "summary": "按人民币结算的单张美元面值充值卡",
                "sort_order": 1,
            },
            {
                "name": "支付测试套餐",
                "slug": "developer-gift-cards",
                "summary": "面向支付通道联调的人民币结算组合套餐",
                "sort_order": 2,
            },
        ]

        for item in categories:
            category, created = ProductCategory.objects.update_or_create(slug=item["slug"], defaults=item)
            action = "创建" if created else "更新"
            self.stdout.write(self.style.SUCCESS(f"{action}分类: {category.name}"))

        samples = [
            {
                "category": ProductCategory.objects.get(slug="openai-token-topup"),
                "title": "1 美元充值卡",
                "slug": "payment-smoke-pack-1usd",
                "summary": "用人民币购买价值 US$1 的充值卡，适合最小金额支付冒烟测试。",
                "description": "用人民币购买价值 1 美元的充值卡，适合验证最小支付金额、支付成功回调和订单状态流转。",
                "face_value": "1.00",
                "token_amount": 100000,
                "price": "9.90",
                "delivery_method": Product.DeliveryMethod.STOCK_CARD,
                "badge": "最小金额",
                "cover_url": "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 5,
            },
            {
                "category": ProductCategory.objects.get(slug="developer-gift-cards"),
                "title": "新手体验套餐（总面值 6 美元）",
                "slug": "decimal-regression-pack-3usd",
                "summary": "人民币一次支付，获取总面值 US$6 的组合套餐，适合新手体验。",
                "description": "面向首次测试的组合套餐，适合验证套餐商品、订单金额汇总和基础支付流程。",
                "face_value": "6.00",
                "token_amount": 600000,
                "price": "46.80",
                "delivery_method": Product.DeliveryMethod.STOCK_CARD,
                "badge": "入门套餐",
                "cover_url": "https://images.unsplash.com/photo-1559526324-593bc073d938?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 5,
            },
            {
                "category": ProductCategory.objects.get(slug="openai-token-topup"),
                "title": "5 美元充值卡",
                "slug": "open-token-5usd",
                "summary": "用人民币购买价值 US$5 的充值卡，适合低额支付与退款测试。",
                "description": "适合轻量测试、支付成功回调、查单和退款流程验证。",
                "face_value": "5.00",
                "token_amount": 500000,
                "price": "39.90",
                "delivery_method": Product.DeliveryMethod.STOCK_CARD,
                "badge": "常用面值",
                "cover_url": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 4,
            },
            {
                "category": ProductCategory.objects.get(slug="openai-token-topup"),
                "title": "10 美元充值卡",
                "slug": "open-token-10usd",
                "summary": "用人民币购买价值 US$10 的充值卡，适合常规支付联调。",
                "description": "适用于日常支付测试、订单查询和自动发货验证，是最常用的中低档测试商品。",
                "face_value": "10.00",
                "token_amount": 1000000,
                "price": "78.00",
                "delivery_method": Product.DeliveryMethod.STOCK_CARD,
                "badge": "主力测试",
                "cover_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 5,
            },
            {
                "category": ProductCategory.objects.get(slug="developer-gift-cards"),
                "title": "日常开发套餐（总面值 15 美元）",
                "slug": "developer-week-pack",
                "summary": "人民币一次支付，获取总面值 US$15 的组合套餐，适合日常开发测试。",
                "description": "适合短周期开发、测试周和脚本批量运行，兼顾人民币支付与较高美元总面值。",
                "face_value": "15.00",
                "token_amount": 1500000,
                "price": "108.00",
                "delivery_method": Product.DeliveryMethod.STOCK_CARD,
                "badge": "人气套餐",
                "cover_url": "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 3,
            },
            {
                "category": ProductCategory.objects.get(slug="developer-gift-cards"),
                "title": "团队联调套餐（总面值 40 美元）",
                "slug": "open-token-20usd",
                "summary": "人民币一次支付，获取总面值 US$40 的组合套餐，适合多人联调。",
                "description": "适合团队共享测试额度、验证中额支付、异步通知重试和订单状态同步。",
                "face_value": "40.00",
                "token_amount": 4000000,
                "price": "299.00",
                "delivery_method": Product.DeliveryMethod.PARTNER_API,
                "provider_sku": "bundle-team-40usd",
                "badge": "团队套餐",
                "cover_url": "https://images.unsplash.com/photo-1556740749-887f6717d7e4?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 0,
            },
            {
                "category": ProductCategory.objects.get(slug="openai-token-topup"),
                "title": "30 美元充值卡",
                "slug": "gateway-integration-pack-30usd",
                "summary": "用人民币购买价值 US$30 的充值卡，适合支付回调和对账联调。",
                "description": "由合作 API 平台自动供货，适合验证中额支付链路、支付回调、商户订单映射和异步通知重试。",
                "face_value": "30.00",
                "token_amount": 3000000,
                "price": "228.00",
                "delivery_method": Product.DeliveryMethod.PARTNER_API,
                "provider_sku": "api-token-30usd",
                "badge": "联调推荐",
                "cover_url": "https://images.unsplash.com/photo-1550565118-3a14e8d0386f?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 0,
            },
            {
                "category": ProductCategory.objects.get(slug="openai-token-topup"),
                "title": "50 美元充值卡",
                "slug": "open-token-50usd",
                "summary": "用人民币购买价值 US$50 的充值卡，适合高频测试与持续补货。",
                "description": "由合作 API 平台自动供货，适合高频业务测试、多项目共用和较高额度联调。",
                "face_value": "50.00",
                "token_amount": 5000000,
                "price": "368.00",
                "delivery_method": Product.DeliveryMethod.PARTNER_API,
                "provider_sku": "api-token-50usd",
                "badge": "高频支付",
                "cover_url": "https://images.unsplash.com/photo-1520607162513-77705c0f0d4a?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 0,
            },
            {
                "category": ProductCategory.objects.get(slug="openai-token-topup"),
                "title": "100 美元充值卡",
                "slug": "enterprise-api-pack-100usd",
                "summary": "用人民币购买价值 US$100 的充值卡，适合大额支付链路测试。",
                "description": "适合验证大额支付、人工复核、风控提醒和长期使用场景下的自动供货流程。",
                "face_value": "100.00",
                "token_amount": 10000000,
                "price": "728.00",
                "delivery_method": Product.DeliveryMethod.PARTNER_API,
                "provider_sku": "api-token-100usd",
                "badge": "大额支付",
                "cover_url": "https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 0,
            },
            {
                "category": ProductCategory.objects.get(slug="developer-gift-cards"),
                "title": "企业压测套餐（总面值 150 美元）",
                "slug": "enterprise-acceptance-pack-200usd",
                "summary": "人民币一次支付，获取总面值 US$150 的组合套餐，适合企业压测与验收。",
                "description": "面向后期正式支付通道验收，适合测试高金额下单、支付成功回调、人工审核和企业级联调流程。",
                "face_value": "150.00",
                "token_amount": 15000000,
                "price": "1068.00",
                "delivery_method": Product.DeliveryMethod.PARTNER_API,
                "provider_sku": "bundle-enterprise-150usd",
                "badge": "企业套餐",
                "cover_url": "https://images.unsplash.com/photo-1520607162513-77705c0f0d4a?auto=format&fit=crop&w=1200&q=80",
                "low_stock_threshold": 0,
            },
        ]

        for item in samples:
            product, created = Product.objects.update_or_create(slug=item["slug"], defaults=item)
            action = "创建" if created else "更新"
            self.stdout.write(self.style.SUCCESS(f"{action}商品: {product.title}"))

        announcements = [
            {
                "title": "全站商品已统一为人民币结算，充值面值按美元展示",
                "body": "商品卡面显示的是美元充值面值，实际下单和结算金额统一按人民币展示。",
                "sort_order": 1,
                "is_pinned": True,
            },
            {
                "title": "支付测试商品已覆盖 1 / 5 / 10 / 30 / 50 / 100 美元和多档套餐",
                "body": "现在可以直接用不同人民币金额的商品做支付通道联调、回调验证和对账测试。",
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

        stock_samples = {
            "payment-smoke-pack-1usd": 16,
            "decimal-regression-pack-3usd": 14,
            "open-token-5usd": 8,
            "open-token-10usd": 12,
            "developer-week-pack": 6,
        }
        for slug, quantity in stock_samples.items():
            product = Product.objects.get(slug=slug)
            prefix = slug.replace("-", "_").upper()
            for index in range(1, quantity + 1):
                plain_code = f"DEMO-{prefix}-{index:04d}"
                code_hash = CardCode.build_code_hash(plain_code)
                card = CardCode.objects.filter(code_hash=code_hash).first()
                if not card:
                    CardCode.objects.create(
                        product=product,
                        code=plain_code,
                        note="演示库存",
                    )

        self.stdout.write(self.style.SUCCESS("演示数据已准备完成。"))
