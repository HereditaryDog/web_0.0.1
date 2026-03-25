from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import EmailVerificationCode, User
from .utils import build_signup_code_response_payload


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountAuthFlowTests(TestCase):
    def test_legacy_login_alias_redirects_to_accounts_login(self):
        response = self.client.get("/login/")
        self.assertRedirects(response, reverse("accounts:login"))

    def test_legacy_signup_alias_redirects_to_accounts_signup(self):
        response = self.client.get("/signup/")
        self.assertRedirects(response, reverse("accounts:signup"))

    def test_send_signup_code_creates_verification_record(self):
        client = Client()
        response = client.post(reverse("accounts:signup_send_code"), {"email": "newuser@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmailVerificationCode.objects.filter(email="newuser@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(response, "cooldown_seconds")

    def test_send_signup_code_rejects_invalid_email(self):
        response = self.client.post(reverse("accounts:signup_send_code"), {"email": "not-an-email"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "请输入有效的邮箱地址。")
        self.assertFalse(EmailVerificationCode.objects.filter(email="not-an-email").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend", DEBUG=True)
    def test_send_signup_code_returns_debug_code_for_local_mail_backend(self):
        response = self.client.post(reverse("accounts:signup_send_code"), {"email": "debug@example.com"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["delivery_mode"], "debug")
        self.assertIn("debug_code", payload)
        self.assertIn("本地调试模式", payload["message"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEBUG=True)
    def test_send_signup_code_hides_debug_code_for_real_mail_backend(self):
        verification = EmailVerificationCode(
            email="prod@example.com",
            purpose=EmailVerificationCode.Purpose.SIGNUP,
            code="654321",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        payload = build_signup_code_response_payload(verification)
        self.assertEqual(payload["delivery_mode"], "email")
        self.assertNotIn("debug_code", payload)
        self.assertEqual(payload["message"], "验证码已发送，请查收邮箱。")

    @patch("accounts.utils.send_mail", side_effect=RuntimeError("smtp unavailable"))
    def test_send_signup_code_cleans_up_record_when_delivery_fails(self, mock_send_mail):
        response = self.client.post(reverse("accounts:signup_send_code"), {"email": "failed@example.com"})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(EmailVerificationCode.objects.filter(email="failed@example.com").exists())
        self.assertEqual(mock_send_mail.call_count, 1)

    def test_signup_requires_valid_email_code(self):
        verification = EmailVerificationCode.objects.create(
            email="verified@example.com",
            purpose=EmailVerificationCode.Purpose.SIGNUP,
            code="123456",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        client = Client()
        response = client.post(
            reverse("accounts:signup"),
            {
                "username": "verified-user",
                "email": "verified@example.com",
                "phone": "13800138000",
                "email_code": "123456",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="verified-user").exists())

    def test_signup_with_email_code_creates_verified_user(self):
        verification = EmailVerificationCode.objects.create(
            email="verified@example.com",
            purpose=EmailVerificationCode.Purpose.SIGNUP,
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        client = Client()
        response = client.post(
            reverse("accounts:signup"),
            {
                "username": "verified-user",
                "email": "verified@example.com",
                "phone": "13800138000",
                "email_code": "123456",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="verified-user")
        verification.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(verification.consumed_at)

    def test_login_supports_username_or_email_with_captcha(self):
        user = User.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            phone="13800138000",
            password="Buyer123!",
            email_verified=True,
        )
        self.assertIsNotNone(user.pk)

        client = Client()
        session = client.session
        session["login_captcha"] = "AB12"
        session.save()

        username_response = client.post(
            reverse("accounts:login"),
            {"username": "buyer", "password": "Buyer123!", "captcha": "AB12"},
        )
        self.assertEqual(username_response.status_code, 302)

        client.logout()
        session = client.session
        session["login_captcha"] = "CD34"
        session.save()

        email_response = client.post(
            reverse("accounts:login"),
            {"username": "buyer@example.com", "password": "Buyer123!", "captcha": "CD34"},
        )
        self.assertEqual(email_response.status_code, 302)

    def test_customer_login_rejects_merchant_account(self):
        User.objects.create_user(
            username="merchant-user",
            email="merchant@example.com",
            phone="13800138088",
            password="Merchant123!",
            is_staff=True,
            is_merchant=True,
        )
        client = Client()
        session = client.session
        session["login_captcha"] = "AB12"
        session.save()

        response = client.post(
            reverse("accounts:login"),
            {"username": "merchant-user", "password": "Merchant123!", "captcha": "AB12"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "商家账号请前往商家登录页")

    def test_merchant_login_rejects_normal_user_account(self):
        User.objects.create_user(
            username="normal-user",
            email="normal@example.com",
            phone="13800138089",
            password="Buyer123!",
            email_verified=True,
        )
        client = Client()
        session = client.session
        session["login_captcha"] = "EF56"
        session.save()

        response = client.post(
            reverse("accounts:merchant_login"),
            {"username": "normal-user", "password": "Buyer123!", "captcha": "EF56"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "该账号不是商家账号，请使用普通用户登录页")

    def test_merchant_login_supports_merchant_account(self):
        User.objects.create_user(
            username="merchant-owner",
            email="merchant-owner@example.com",
            phone="13800138090",
            password="Merchant123!",
            is_staff=True,
            is_merchant=True,
        )
        client = Client()
        session = client.session
        session["login_captcha"] = "GH78"
        session.save()

        response = client.post(
            reverse("accounts:merchant_login"),
            {"username": "merchant-owner", "password": "Merchant123!", "captcha": "GH78"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("shop:merchant_dashboard"))

    def test_login_rejects_invalid_captcha(self):
        User.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            phone="13800138000",
            password="Buyer123!",
            email_verified=True,
        )
        client = Client()
        session = client.session
        session["login_captcha"] = "WXYZ"
        session.save()

        response = client.post(
            reverse("accounts:login"),
            {"username": "buyer", "password": "Buyer123!", "captcha": "1234"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "验证码不正确")

    def test_login_captcha_refresh_endpoint_returns_new_code(self):
        client = Client()
        response = client.get(reverse("accounts:login_captcha"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "captcha")

    def test_login_page_uses_configured_site_name(self):
        response = self.client.get(reverse("accounts:login"), HTTP_HOST="127.0.0.1:8000")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "G-Master发卡网")

    def test_login_page_contains_password_reset_link(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("password_reset"))
        self.assertContains(response, reverse("accounts:merchant_login"))

    def test_merchant_login_page_renders_independent_copy(self):
        response = self.client.get(reverse("accounts:merchant_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "登录商家后台")
        self.assertContains(response, "返回商城登录")

    def test_password_reset_request_sends_email(self):
        User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            phone="13800138002",
            password="Buyer123!",
            email_verified=True,
        )
        response = self.client.post(reverse("password_reset"), {"email": "reset@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    @override_settings(SITE_BASE_URL="https://account.example.com")
    def test_password_reset_request_uses_configured_public_base_url(self):
        User.objects.create_user(
            username="reset-public-user",
            email="reset-public@example.com",
            phone="13800138006",
            password="Buyer123!",
            email_verified=True,
        )
        response = self.client.post(reverse("password_reset"), {"email": "reset-public@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertIn("https://account.example.com/accounts/reset/", mail.outbox[0].body)

    def test_password_reset_confirm_updates_password(self):
        user = User.objects.create_user(
            username="recover-user",
            email="recover@example.com",
            phone="13800138003",
            password="OldPass123!",
            email_verified=True,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_url = reverse("password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})

        response = self.client.get(confirm_url, follow=True)
        self.assertEqual(response.status_code, 200)

        post_response = self.client.post(
            response.request["PATH_INFO"],
            {"new_password1": "NewPass123!", "new_password2": "NewPass123!"},
            follow=True,
        )
        self.assertRedirects(post_response, reverse("password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPass123!"))

    def test_account_center_contains_password_change_link(self):
        user = User.objects.create_user(
            username="account-user",
            email="account@example.com",
            phone="13800138004",
            password="Buyer123!",
            email_verified=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("shop:account_center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("password_change"))

    def test_password_change_updates_password_for_authenticated_user(self):
        user = User.objects.create_user(
            username="change-user",
            email="change@example.com",
            phone="13800138005",
            password="OldPass123!",
            email_verified=True,
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "OldPass123!",
                "new_password1": "BrandNew123!",
                "new_password2": "BrandNew123!",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("password_change_done"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("BrandNew123!"))
