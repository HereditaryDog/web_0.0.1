from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="邮箱")
    display_name = forms.CharField(label="昵称", max_length=80)
    phone = forms.CharField(label="手机号", max_length=32, required=False)

    class Meta:
        model = User
        fields = ("username", "display_name", "email", "phone", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.display_name = self.cleaned_data["display_name"]
        user.phone = self.cleaned_data["phone"]
        if commit:
            user.save()
        return user
