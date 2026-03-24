from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from shop.deployment_checks import run_readiness_checks
from shop.models import (
    CardCode,
    DeliveryRecord,
    HelpArticle,
    InventoryImportBatch,
    Order,
    Product,
    ProductCategory,
    SensitiveOperationLog,
    SiteAnnouncement,
    SupportTicket,
    SupportTicketMessage,
)
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
        self.related_product = Product.objects.create(
            category=self.category,
            title="Test Token Card Pro",
            slug="test-token-card-pro",
            summary="测试商品进阶版",
            description="测试商品进阶版详情",
            face_value="20.00",
            token_amount=2000000,
            price="118.00",
            delivery_method=Product.DeliveryMethod.PARTNER_API,
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

    def test_guest_order_lookup_masks_delivery_codes_in_initial_html(self):
        client = Client()
        self.assertTrue(client.login(username="buyer", password="Buyer123!"))
        client.post(reverse("shop:create_order", args=[self.product.slug]), {"quantity": 1})
        order = Order.objects.get(user=self.buyer)
        client.post(reverse("shop:start_payment", args=[order.order_no]))
        client.post(reverse("shop:mock_pay", args=[order.order_no]))
        client.logout()
        response = client.post(
            reverse("shop:order_lookup"),
            {"order_no": order.order_no, "email": self.buyer.email},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "CODE-0001")
        self.assertContains(response, "CODE...0001")

    def test_guest_delivery_reveal_requires_matching_email_token(self):
        client = Client()
        self.assertTrue(client.login(username="buyer", password="Buyer123!"))
        client.post(reverse("shop:create_order", args=[self.product.slug]), {"quantity": 1})
        order = Order.objects.get(user=self.buyer)
        client.post(reverse("shop:start_payment", args=[order.order_no]))
        client.post(reverse("shop:mock_pay", args=[order.order_no]))
        client.logout()
        lookup_response = client.post(
            reverse("shop:order_lookup"),
            {"order_no": order.order_no, "email": self.buyer.email},
        )
        self.assertEqual(lookup_response.status_code, 200)
        guest_token = lookup_response.context["guest_access_token"]
        delivery = DeliveryRecord.objects.get(order_item__order=order)
        invalid_response = client.post(
            reverse("shop:delivery_reveal", args=[order.order_no, delivery.id]),
            {"access_token": guest_token[:-1] + ("A" if guest_token[-1] != "A" else "B")},
        )
        self.assertEqual(invalid_response.status_code, 403)

    def test_help_center_and_article_detail_render(self):
        client = Client()
        list_response = client.get(reverse("shop:help_center"))
        detail_response = client.get(reverse("shop:help_article_detail", args=[self.article.slug]))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(list_response, "测试教程")
        self.assertContains(detail_response, "教程正文")

    def test_product_detail_renders_related_product_and_purchase_copy(self):
        client = Client()
        response = client.get(reverse("shop:product_detail", args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "商品说明")
        self.assertContains(response, "同类商品推荐")
        self.assertContains(response, self.related_product.title)

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

    @override_settings(SITE_BASE_URL="")
    def test_merchant_can_resend_delivery_email_uses_request_host_when_public_base_url_not_configured(self):
        self.client.force_login(self.owner)
        delivered_code = DeliveryRecord.objects.get(order_item__order=self.completed_order).reveal_display_code()
        response = self.client.post(
            reverse("shop:merchant_order_action", args=[self.completed_order.order_no]),
            {"action": "resend_delivery"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.completed_order.order_no, mail.outbox[0].body)
        self.assertNotIn(delivered_code, mail.outbox[0].body)
        self.assertIn("不会通过邮件直接重发完整发货内容", mail.outbox[0].body)
        self.assertIn("http://testserver/order-lookup/", mail.outbox[0].body)
        self.assertTrue(
            SensitiveOperationLog.objects.filter(
                action=SensitiveOperationLog.Action.SEND_DELIVERY_REMINDER,
                order=self.completed_order,
            ).exists()
        )

    @override_settings(SITE_BASE_URL="https://store.example.com")
    def test_merchant_can_resend_delivery_email_uses_configured_public_base_url(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("shop:merchant_order_action", args=[self.completed_order.order_no]),
            {"action": "resend_delivery"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://store.example.com/order-lookup/", mail.outbox[0].body)
        self.assertIn("https://store.example.com/me/", mail.outbox[0].body)

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

    def test_card_codes_are_encrypted_at_rest(self):
        card = CardCode.objects.create(product=self.product, code="SECRET-CODE-1234", note="安全测试")
        card.refresh_from_db()
        self.assertNotEqual(card.code, "SECRET-CODE-1234")
        self.assertTrue(card.code.startswith("gAAAAA"))
        self.assertEqual(card.reveal_code(), "SECRET-CODE-1234")

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
        self.assertTrue(CardCode.objects.filter(code_hash=CardCode.build_code_hash("NEW-CODE-1")).exists())
        self.assertTrue(CardCode.objects.filter(code_hash=CardCode.build_code_hash("NEW-CODE-2")).exists())
        batch = InventoryImportBatch.objects.latest("created_at")
        self.assertEqual(batch.imported_count, 2)
        self.assertEqual(batch.duplicate_count, 2)

    def test_inventory_page_masks_plaintext_codes(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("shop:merchant_inventory"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "OPS-CODE-0001")
        self.assertContains(response, "OPS-...0001")

    def test_inventory_code_reveal_returns_plaintext_and_logs(self):
        self.client.force_login(self.owner)
        card = CardCode.objects.get(code_hash=CardCode.build_code_hash("OPS-CODE-0001"))
        response = self.client.post(reverse("shop:merchant_inventory_code_reveal", args=[card.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], "OPS-CODE-0001")
        self.assertTrue(
            SensitiveOperationLog.objects.filter(
                action=SensitiveOperationLog.Action.REVEAL_CARD_CODE,
                card_code=card,
            ).exists()
        )

    def test_delivery_reveal_returns_plaintext_and_logs_for_merchant(self):
        self.client.force_login(self.owner)
        delivery = DeliveryRecord.objects.get(order_item__order=self.completed_order)
        response = self.client.post(reverse("shop:delivery_reveal", args=[self.completed_order.order_no, delivery.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], delivery.reveal_display_code())
        self.assertTrue(
            SensitiveOperationLog.objects.filter(
                action=SensitiveOperationLog.Action.REVEAL_DELIVERY_CODE,
                delivery_record=delivery,
            ).exists()
        )


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

    def test_order_detail_masks_delivery_codes_in_initial_html(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("shop:order_detail", args=[self.completed_order.order_no]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "REPEAT-CODE-001")

    def test_order_delivery_reveal_requires_owner_or_merchant(self):
        other = User.objects.create_user(username="other", password="Other123!", email="other@example.com")
        delivery = DeliveryRecord.objects.get(order_item__order=self.completed_order)
        self.client.force_login(other)
        response = self.client.post(reverse("shop:delivery_reveal", args=[self.completed_order.order_no, delivery.id]))
        self.assertEqual(response.status_code, 403)


class SecurityMiddlewareTests(TestCase):
    @override_settings(ADMIN_ALLOWED_IPS=["10.0.0.1"])
    def test_admin_ip_allowlist_blocks_non_allowed_ip(self):
        response = self.client.get("/admin/", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 403)

    @override_settings(MERCHANT_ALLOWED_IPS=["10.0.0.1"])
    def test_merchant_ip_allowlist_blocks_non_allowed_ip(self):
        owner = User.objects.create_user(
            username="owner-sec",
            password="ChangeMe123!",
            email="owner-sec@example.com",
            is_staff=True,
            is_merchant=True,
        )
        self.client.force_login(owner)
        response = self.client.get(reverse("shop:merchant_dashboard"), REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 403)


class ReadinessChecksTests(TestCase):
    @override_settings(
        DEBUG=False,
        CARD_SECRET_KEY="test-card-secret",
        SITE_BASE_URL="https://staging.example.com",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="noreply@example.com",
        PARTNER_API_BASE_URL="https://partner.example.com",
        PARTNER_API_KEY="partner-token",
        PAYMENT_ENABLE_MOCK_GATEWAY=False,
        PAYMENT_ENABLE_STRIPE_GATEWAY=True,
        STRIPE_SECRET_KEY="sk_test_123",
    )
    def test_readiness_checks_can_report_external_test_ready(self):
        result = run_readiness_checks()
        self.assertTrue(result["ok"])
        self.assertTrue(result["external_user_test_ready"])

    def test_readiness_endpoint_returns_json(self):
        response = self.client.get(reverse("shop:readiness"))
        self.assertIn(response.status_code, (200, 503))
        self.assertContains(response, "internal_test_ready")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SupportSystemTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="support-owner",
            password="ChangeMe123!",
            email="support-owner@example.com",
            is_staff=True,
            is_merchant=True,
        )
        self.user = User.objects.create_user(
            username="support-user",
            password="Buyer123!",
            email="support-user@example.com",
            email_verified=True,
        )
        self.other = User.objects.create_user(
            username="other-user",
            password="Other123!",
            email="other-user@example.com",
        )
        category = ProductCategory.objects.create(name="客服分类", slug="support-category")
        product = Product.objects.create(
            category=category,
            title="Support Card",
            slug="support-card",
            summary="客服测试商品",
            description="客服测试商品详情",
            face_value="10.00",
            token_amount=1000,
            price="10.00",
            delivery_method=Product.DeliveryMethod.STOCK_CARD,
            is_active=True,
        )
        self.order = create_single_item_order(self.user, product, 1)

    def test_authenticated_user_can_create_support_ticket(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("shop:support"),
            {
                "order": self.order.id,
                "category": SupportTicket.Category.ORDER,
                "priority": SupportTicket.Priority.NORMAL,
                "subject": "订单状态异常",
                "contact_email": self.user.email,
                "body": "支付后长时间未更新，请帮忙核查。",
            },
        )
        ticket = SupportTicket.objects.get()
        self.assertRedirects(response, reverse("shop:support_ticket_detail", args=[ticket.ticket_no]))
        self.assertEqual(ticket.user, self.user)
        self.assertEqual(ticket.order, self.order)
        self.assertEqual(ticket.status, SupportTicket.Status.PENDING_SUPPORT)
        self.assertEqual(ticket.messages.count(), 1)
        self.assertEqual(ticket.messages.first().sender_role, SupportTicketMessage.SenderRole.USER)

    def test_user_cannot_access_other_users_ticket(self):
        ticket = SupportTicket.objects.create(
            user=self.user,
            order=self.order,
            contact_email=self.user.email,
            category=SupportTicket.Category.ORDER,
            priority=SupportTicket.Priority.NORMAL,
            subject="订单问题",
        )
        SupportTicketMessage.objects.create(
            ticket=ticket,
            sender=self.user,
            sender_role=SupportTicketMessage.SenderRole.USER,
            body="需要客服处理。",
        )
        ticket.status = SupportTicket.Status.PENDING_SUPPORT
        ticket.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.other)
        response = self.client.get(reverse("shop:support_ticket_detail", args=[ticket.ticket_no]))
        self.assertEqual(response.status_code, 404)

    def test_merchant_can_reply_and_update_support_ticket(self):
        ticket = SupportTicket.objects.create(
            user=self.user,
            order=self.order,
            contact_email=self.user.email,
            category=SupportTicket.Category.ORDER,
            priority=SupportTicket.Priority.NORMAL,
            subject="订单问题",
        )
        SupportTicketMessage.objects.create(
            ticket=ticket,
            sender=self.user,
            sender_role=SupportTicketMessage.SenderRole.USER,
            body="请帮我查一下发货情况。",
        )
        ticket.status = SupportTicket.Status.PENDING_SUPPORT
        ticket.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("shop:merchant_support_ticket_detail", args=[ticket.ticket_no]),
            {"status": SupportTicket.Status.PENDING_USER, "body": "已经核验订单，请补充一下异常截图。"},
        )
        self.assertRedirects(response, reverse("shop:merchant_support_ticket_detail", args=[ticket.ticket_no]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.PENDING_USER)
        self.assertEqual(ticket.messages.count(), 2)
        self.assertEqual(ticket.messages.last().sender_role, SupportTicketMessage.SenderRole.SUPPORT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(ticket.ticket_no, mail.outbox[0].body)

    def test_merchant_status_only_update_sends_notification(self):
        ticket = SupportTicket.objects.create(
            user=self.user,
            order=self.order,
            contact_email=self.user.email,
            category=SupportTicket.Category.ORDER,
            priority=SupportTicket.Priority.NORMAL,
            subject="状态变更测试",
        )
        SupportTicketMessage.objects.create(
            ticket=ticket,
            sender=self.user,
            sender_role=SupportTicketMessage.SenderRole.USER,
            body="请更新一下状态。",
        )
        ticket.status = SupportTicket.Status.PENDING_SUPPORT
        ticket.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("shop:merchant_support_ticket_detail", args=[ticket.ticket_no]),
            {"status": SupportTicket.Status.RESOLVED, "body": ""},
        )
        self.assertRedirects(response, reverse("shop:merchant_support_ticket_detail", args=[ticket.ticket_no]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.RESOLVED)
        self.assertEqual(ticket.messages.last().sender_role, SupportTicketMessage.SenderRole.SYSTEM)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("已解决", mail.outbox[0].body)

    def test_user_cannot_reply_to_closed_ticket(self):
        ticket = SupportTicket.objects.create(
            user=self.user,
            order=self.order,
            contact_email=self.user.email,
            category=SupportTicket.Category.ORDER,
            priority=SupportTicket.Priority.NORMAL,
            subject="已关闭工单",
            status=SupportTicket.Status.CLOSED,
            closed_at=timezone.now(),
        )
        SupportTicketMessage.objects.create(
            ticket=ticket,
            sender=self.owner,
            sender_role=SupportTicketMessage.SenderRole.SUPPORT,
            body="此工单已关闭。",
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("shop:support_ticket_detail", args=[ticket.ticket_no]),
            {"body": "我还想继续补充说明"},
            follow=True,
        )
        self.assertRedirects(response, reverse("shop:support_ticket_detail", args=[ticket.ticket_no]))
        self.assertEqual(ticket.messages.count(), 1)
