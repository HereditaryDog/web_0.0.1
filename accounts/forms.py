from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.utils import timezone

from .models import EmailVerificationCode, User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="邮箱地址")
    phone = forms.CharField(label="手机号", max_length=32)
    email_code = forms.CharField(label="邮箱验证码", max_length=6)

    class Meta:
        model = User
        fields = ("username", "email", "phone", "email_code", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("该邮箱已经注册。")
        return email

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not phone:
            raise forms.ValidationError("手机号不能为空。")
        return phone

    def clean_email_code(self):
        code = self.cleaned_data["email_code"].strip()
        email = self.cleaned_data.get("email", "").strip().lower()
        verification = (
            EmailVerificationCode.objects.filter(
                email__iexact=email,
                purpose=EmailVerificationCode.Purpose.SIGNUP,
                code=code,
                consumed_at__isnull=True,
                expires_at__gte=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )
        if not verification:
            raise forms.ValidationError("邮箱验证码无效或已过期。")
        self._matched_verification = verification
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data["phone"]
        user.display_name = self.cleaned_data["username"]
        user.email_verified = True
        user.email_verified_at = timezone.now()
        if commit:
            user.save()
            matched = getattr(self, "_matched_verification", None)
            if matched:
                matched.mark_consumed()
        return user


class AccountLoginForm(AuthenticationForm):
    username = forms.CharField(label="账号", max_length=254)
    password = forms.CharField(label="密码", strip=False, widget=forms.PasswordInput)
    captcha = forms.CharField(label="验证码", max_length=8)

    error_messages = {
        "invalid_login": "账号或密码不正确，请重新输入。",
        "invalid_captcha": "验证码不正确，请重新输入。",
        "inactive": "该账号已被停用。",
        "merchant_account": "商家账号请前往商家登录页。",
        "non_merchant_account": "该账号不是商家账号，请使用普通用户登录页。",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        self.fields["username"].widget.attrs.update({"placeholder": "用户名或邮箱地址"})
        self.fields["captcha"].widget.attrs.update({"placeholder": "输入图形验证码"})

    def clean_captcha(self):
        captcha = self.cleaned_data["captcha"].strip().upper()
        expected = (self.request.session.get("login_captcha") or "").upper()
        if not captcha or captcha != expected:
            raise forms.ValidationError(self.error_messages["invalid_captcha"])
        return captcha

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                )
            self.confirm_login_allowed(self.user_cache)
        return cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or user.is_superuser or user.is_merchant:
            raise forms.ValidationError(
                self.error_messages["merchant_account"],
                code="merchant_account",
            )


class MerchantLoginForm(AccountLoginForm):
    def confirm_login_allowed(self, user):
        AuthenticationForm.confirm_login_allowed(self, user)
        if not (user.is_staff or user.is_superuser or user.is_merchant):
            raise forms.ValidationError(
                self.error_messages["non_merchant_account"],
                code="non_merchant_account",
            )


class AccountPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(label="邮箱地址")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"placeholder": "输入注册时使用的邮箱地址"})


class AccountSetPasswordForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].label = "新密码"
        self.fields["new_password2"].label = "确认新密码"
        self.fields["new_password1"].widget.attrs.update({"placeholder": "输入新的登录密码"})
        self.fields["new_password2"].widget.attrs.update({"placeholder": "再次输入新密码"})


class AccountPasswordChangeForm(PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["old_password"].label = "当前密码"
        self.fields["new_password1"].label = "新密码"
        self.fields["new_password2"].label = "确认新密码"
        self.fields["old_password"].widget.attrs.update({"placeholder": "输入当前登录密码"})
        self.fields["new_password1"].widget.attrs.update({"placeholder": "输入新的登录密码"})
        self.fields["new_password2"].widget.attrs.update({"placeholder": "再次输入新密码"})
