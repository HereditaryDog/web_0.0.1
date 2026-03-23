from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from shop.models import CardCode, DeliveryRecord, HelpArticle, InventoryImportBatch, Order, Product, ProductCategory, SiteAnnouncement
from shop.services.order_flow import create_single_item_order, mark_order_paid
from shop.services.payment import get_default_gateway_code, list_active_payment_gateways, list_reserved_payment_gateways


class StoreOrderFlowTests(TestCase):
    def setUp(self):
        self.category = ProductCategory.objects.create(name="测试分类", slug="test-category")
        SiteAnnouncement.objects.create(title="测试公告", body="公告内容")
        self.article = HelpArticle.objects.create(
            title="测试教程",
            slug="test-guide",
            section=HelpArticle.Section.GUIDE,
            summary="教程摘要",
            content="教程正文",
            is_featured=True,
        )
        self.buyer = User.objects.create_user(
            username="buyer",
            password="Buyer123!",
            email="buyer@example.com",
            display_name="Buyer",
        )
        self.product = Product.objects.create(
            category=self.category,
            title="Test Token Card",
            slug="test-token-card",
            summary="测试商品",
            description="测试商品详情",
            face_value="10.00",
            token_amount=1000000,
            price="68.00",
            delivery_method=Product.DeliveryMethod.STOCK_CARD,
            is_active=True,
        )
        CardCode.objects.create(product=self.product, code="CODE-0001")

    def test_storefront_renders_category_and_announcement(self):
        client = Client()
        response = client.get(reverse("shop:storefront"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "测试分类")
        self.assertContains(response, "测试公告")
        self.assertContains(response, "测试教程")

    def test_mock_payment_completes_order_and_delivers_code(self):
        client = Client()
        self.assertTrue(client.login(username="buyer", password="Buyer123!"))

        response = client.post(reverse("shop:create_order", args=[self.product.slug]), {"quantity": 1})
        self.assertEqual(response.status_code, 302)

        order = Order.objects.get(user=self.buyer)
        pay_response = client.post(reverse("shop:start_payment", args=[order.order_no]))
        self.assertEqual(pay_response.status_code, 302)

        finish_response = client.post(reverse("shop:mock_pay", args=[order.order_no]))
        self.assertEqual(finish_response.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(DeliveryRecord.objects.filter(order_item__order=order).count(), 1)

    def test_guest_order_lookup_works_with_order_number_and_email(self):
        client = Client()
        self.assertTrue(client.login(username="buyer", password="Buyer123!"))
        client.post(reverse("shop:create_order", args=[self.product.slug]), {"quantity": 1})
        order = Order.objects.get(user=self.buyer)

        client.logout()
        response = client.post(
            reverse("shop:order_lookup"),
            {"order_no": order.order_no, "email": self.buyer.email},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_no)

    def test_help_center_and_article_detail_render(self):
        client = Client()
        list_response = client.get(reverse("shop:help_center"))
        detail_response = client.get(reverse("shop:help_article_detail", args=[self.article.slug]))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(list_response, "测试教程")
        self.assertContains(detail_response, "教程正文")

    def test_support_page_renders(self):
        client = Client()
        response = client.get(reverse("shop:support"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "客服与售后支持")

    def test_checkout_page_shows_active_and_reserved_payment_gateways(self):
        client = Client()
        self.assertTrue(client.login(username="buyer", password="Buyer123!"))
        client.post(reverse("shop:create_order", args=[self.product.slug]), {"quantity": 1})
        order = Order.objects.get(user=self.buyer)

        response = client.get(reverse("shop:checkout", args=[order.order_no]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "模拟支付")
        self.assertContains(response, "支付宝")
        self.assertContains(response, "微信支付")
        self.assertContains(response, "USDT")
        self.assertContains(response, "银行卡转账")

    def test_authenticated_storefront_shows_account_center_entry(self):
        client = Client()
        self.assertTrue(client.login(username="buyer", password="Buyer123!"))
        response = client.get(reverse("shop:storefront"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "账号中心")
        self.assertContains(response, reverse("shop:account_center"))

    def test_payment_gateway_registry_exposes_future_channels(self):
        active_codes = [gateway.code for gateway in list_active_payment_gateways()]
        reserved_codes = [gateway.code for gateway in list_reserved_payment_gateways()]
        self.assertIn(get_default_gateway_code(), active_codes)
        self.assertIn("alipay", reserved_codes)
        self.assertIn("wechat_pay", reserved_codes)
        self.assertIn("usdt", reserved_codes)
        self.assertIn("bank_transfer", reserved_codes)


class MerchantDashboardTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="ChangeMe123!",
            email="owner@example.com",
            display_name="Owner",
            is_staff=True,
            is_merchant=True,
        )

    def test_merchant_pages_require_authenticated_merchant(self):
        client = Client()
        response = client.get(reverse("shop:merchant_dashboard"))
        self.assertEqual(response.status_code, 302)

        self.assertTrue(client.login(username="owner", password="ChangeMe123!"))
        self.assertEqual(client.get(reverse("shop:merchant_dashboard")).status_code, 200)
        self.assertEqual(client.get(reverse("shop:merchant_products")).status_code, 200)
        self.assertEqual(client.get(reverse("shop:merchant_inventory")).status_code, 200)
        self.assertEqual(client.get(reverse("shop:merchant_orders")).status_code, 200)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MerchantOperationsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="ChangeMe123!",
            email="owner@example.com",
            display_name="Owner",
            is_staff=True,
            is_merchant=True,
        )
        self.buyer = User.objects.create_user(
            username="buyer2",
            password="Buyer123!",
            email="buyer2@example.com",
            display_name="Buyer 2",
        )
        self.category = ProductCategory.objects.create(name="运营分类", slug="ops-category")
        self.product = Product.objects.create(
            category=self.category,
            title="Ops Card",
            slug="ops-card",
            summary="运营商品",
            description="运营商品详情",
            face_value="20.00",
            token_amount=2000000,
            price="149.00",
            delivery_method=Product.DeliveryMethod.STOCK_CARD,
            low_stock_threshold=5,
            is_active=True,
        )
        CardCode.objects.create(product=self.product, code="OPS-CODE-0001")
        CardCode.objects.create(product=self.product, code="OPS-CODE-EXIST")
        self.completed_order = create_single_item_order(self.buyer, self.product, 1)
        mark_order_paid(self.completed_order, provider="mock", reference="mock-completed")
        self.pending_order = create_single_item_order(self.buyer, self.product, 1)

    def test_merchant_order_filters_by_query_and_payment_status(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("shop:merchant_orders"),
            {"query": self.buyer.email, "payment_status": Order.PaymentStatus.PAID},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.completed_order.order_no)
        self.assertNotContains(response, self.pending_order.order_no)

    def test_merchant_can_mark_order_failed(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("shop:merchant_order_action", args=[self.pending_order.order_no]),
            {"action": "mark_failed", "merchant_note": "用户反馈订单异常。"},
        )
        self.assertEqual(response.status_code, 302)
        self.pending_order.refresh_from_db()
        self.assertEqual(self.pending_order.status, Order.Status.FAILED)
        self.assertEqual(self.pending_order.merchant_note, "用户反馈订单异常。")

    def test_merchant_can_resend_delivery_email(self):
        self.client.force_login(self.owner)
        delivered_code = DeliveryRecord.objects.get(order_item__order=self.completed_order).display_code
        response = self.client.post(
            reverse("shop:merchant_order_action", args=[self.completed_order.order_no]),
            {"action": "resend_delivery"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.completed_order.order_no, mail.outbox[0].body)
        self.assertIn(delivered_code, mail.outbox[0].body)

    def test_product_filters_and_toggle_status(self):
        self.client.force_login(self.owner)
        inactive_product = Product.objects.create(
            category=self.category,
            title="Hidden Card",
            slug="hidden-card",
            summary="隐藏商品",
            description="隐藏商品详情",
            face_value="10.00",
            token_amount=1000,
            price="10.00",
            delivery_method=Product.DeliveryMethod.PARTNER_API,
            is_active=False,
        )
        response = self.client.get(reverse("shop:merchant_products"), {"query": "hidden", "active": "inactive"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, inactive_product.title)
        toggle_response = self.client.post(reverse("shop:merchant_product_toggle", args=[inactive_product.id]))
        self.assertEqual(toggle_response.status_code, 302)
        inactive_product.refresh_from_db()
        self.assertTrue(inactive_product.is_active)

    def test_inventory_preview_and_import_history(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("shop:merchant_inventory"),
            {
                "product": self.product.id,
                "note": "批量补货",
                "codes": "OPS-CODE-EXIST\nNEW-CODE-1\nNEW-CODE-1\nNEW-CODE-2",
                "intent": "preview",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "导入预览")
        self.assertContains(response, "NEW-CODE-1")
        import_response = self.client.post(
            reverse("shop:merchant_inventory"),
            {
                "product": self.product.id,
                "note": "批量补货",
                "codes": "OPS-CODE-EXIST\nNEW-CODE-1\nNEW-CODE-1\nNEW-CODE-2",
                "intent": "import",
            },
        )
        self.assertEqual(import_response.status_code, 302)
        self.assertTrue(CardCode.objects.filter(code="NEW-CODE-1").exists())
        self.assertTrue(CardCode.objects.filter(code="NEW-CODE-2").exists())
        batch = InventoryImportBatch.objects.latest("created_at")
        self.assertEqual(batch.imported_count, 2)
        self.assertEqual(batch.duplicate_count, 2)


class AccountCenterEnhancementTests(TestCase):
    def setUp(self):
        self.category = ProductCategory.objects.create(name="用户中心分类", slug="account-category")
        self.user = User.objects.create_user(
            username="buyer3",
            password="Buyer123!",
            email="buyer3@example.com",
            display_name="Buyer 3",
            email_verified=True,
        )
        self.product = Product.objects.create(
            category=self.category,
            title="Repeat Card",
            slug="repeat-card",
            summary="可复购商品",
            description="可复购商品详情",
            face_value="30.00",
            token_amount=3000000,
            price="88.00",
            delivery_method=Product.DeliveryMethod.STOCK_CARD,
            is_active=True,
        )
        CardCode.objects.create(product=self.product, code="REPEAT-CODE-001")
        CardCode.objects.create(product=self.product, code="REPEAT-CODE-002")
        self.completed_order = create_single_item_order(self.user, self.product, 1)
        mark_order_paid(self.completed_order, provider="mock", reference="mock-repeat")
        self.pending_order = create_single_item_order(self.user, self.product, 1)

    def test_account_center_filters_orders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("shop:account_center"), {"status": Order.Status.COMPLETED})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.completed_order.order_no)
        self.assertNotContains(response, self.pending_order.order_no)

    def test_user_can_reorder_from_account_center(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("shop:reorder", args=[self.completed_order.order_no]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 3)
