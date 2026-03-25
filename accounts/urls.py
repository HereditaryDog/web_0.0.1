from django.urls import path

from .views import AccountLoginView, MerchantLoginView, RefreshLoginCaptchaView, SendSignupCodeView, SignUpView

urlpatterns = [
    path("login/", AccountLoginView.as_view(), name="login"),
    path("merchant/login/", MerchantLoginView.as_view(), name="merchant_login"),
    path("login/captcha/", RefreshLoginCaptchaView.as_view(), name="login_captcha"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("signup/send-code/", SendSignupCodeView.as_view(), name="signup_send_code"),
]
