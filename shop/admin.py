from django.contrib import admin

from .models import (
    CardCode,
    DeliveryRecord,
    HelpArticle,
    Order,
    OrderItem,
    PaymentAttempt,
    Product,
    ProductCategory,
    SiteAnnouncement,
)

admin.site.site_header = "web_0.0.1 商城后台"
admin.site.site_title = "web_0.0.1"
admin.site.index_title = "商城管理"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_title", "quantity", "unit_price", "line_total")


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SiteAnnouncement)
class SiteAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_pinned", "sort_order", "is_active", "created_at")
    list_filter = ("is_active", "is_pinned")
    search_fields = ("title", "body")


@admin.register(HelpArticle)
class HelpArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "sort_order", "is_published", "is_featured")
    list_filter = ("section", "is_published", "is_featured")
    search_fields = ("title", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "price", "delivery_method", "is_active", "is_featured")
    list_filter = ("category", "delivery_method", "is_active", "is_featured")
    search_fields = ("title", "slug", "provider_sku")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(CardCode)
class CardCodeAdmin(admin.ModelAdmin):
    list_display = ("product", "code", "status", "sold_at")
    list_filter = ("status", "product")
    search_fields = ("code", "note")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "user", "contact_email", "status", "payment_status", "total_amount", "created_at")
    list_filter = ("status", "payment_status", "payment_provider")
    search_fields = ("order_no", "payment_reference", "contact_email", "user__username", "user__email")
    inlines = [OrderItemInline]


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    list_display = ("order_item", "source", "display_code", "delivered_at")
    list_filter = ("source",)
    search_fields = ("display_code", "order_item__order__order_no")


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "reference", "status", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("reference", "order__order_no")
