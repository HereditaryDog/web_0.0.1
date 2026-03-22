from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("商户信息", {"fields": ("display_name", "phone", "is_merchant")}),
    )
    list_display = ("username", "email", "display_name", "is_staff", "is_merchant")
    search_fields = ("username", "email", "display_name", "phone")
