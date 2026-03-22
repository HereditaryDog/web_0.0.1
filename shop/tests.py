from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from shop.models import CardCode, DeliveryRecord, HelpArticle, Order, Product, ProductCategory, SiteAnnouncement


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
