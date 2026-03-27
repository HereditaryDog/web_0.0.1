from django.contrib import admin

from .models import (
    CardCode,
    DeliveryRecord,
    HelpArticle,
    InventoryImportBatch,
    Order,
    OrderItem,
    PaymentAttempt,
    Product,
    ProductCategory,
    SensitiveOperationLog,
    SiteAnnouncement,
    SupportTicket,
    SupportTicketMessage,
)

admin.site.site_header = "G-MasterToken 商城后台"
admin.site.site_title = "G-MasterToken"
admin.site.index_title = "商城管理"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_title", "quantity", "unit_price", "line_total")


class SupportTicketMessageInline(admin.TabularInline):
    model = SupportTicketMessage
    extra = 0
    readonly_fields = ("sender", "sender_role", "body", "created_at")


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
    list_display = ("title", "category", "price", "delivery_method", "low_stock_threshold", "is_active", "is_featured")
    list_filter = ("category", "delivery_method", "is_active", "is_featured")
    search_fields = ("title", "slug", "provider_sku")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(CardCode)
class CardCodeAdmin(admin.ModelAdmin):
    list_display = ("product", "masked_code_display", "status", "sold_at")
    list_filter = ("status", "product")
    search_fields = ("note", "product__title")

    def masked_code_display(self, obj):
        return obj.masked_code

    masked_code_display.short_description = "卡密掩码"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_no",
        "user",
        "contact_email",
        "status",
        "payment_status",
        "total_amount",
        "merchant_note",
        "created_at",
    )
    list_filter = ("status", "payment_status", "payment_provider")
    search_fields = ("order_no", "payment_reference", "contact_email", "user__username", "user__email")
    inlines = [OrderItemInline]


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    list_display = ("order_item", "source", "masked_display_code", "delivered_at")
    list_filter = ("source",)
    search_fields = ("order_item__order__order_no",)

    def masked_display_code(self, obj):
        return obj.masked_display_code

    masked_display_code.short_description = "交付内容掩码"


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "reference", "status", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("reference", "order__order_no")


@admin.register(InventoryImportBatch)
class InventoryImportBatchAdmin(admin.ModelAdmin):
    list_display = ("product", "operator", "imported_count", "duplicate_count", "created_at")
    list_filter = ("product",)
    search_fields = ("product__title", "note", "duplicate_sample", "operator__username")


@admin.register(SensitiveOperationLog)
class SensitiveOperationLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "order", "ip_address", "created_at")
    list_filter = ("action",)
    search_fields = ("order__order_no", "actor__username", "note")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_no", "subject", "user", "category", "priority", "status", "last_message_at")
    list_filter = ("status", "category", "priority")
    search_fields = ("ticket_no", "subject", "contact_email", "user__username", "order__order_no")
    inlines = [SupportTicketMessageInline]


@admin.register(SupportTicketMessage)
class SupportTicketMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "sender", "sender_role", "created_at")
    list_filter = ("sender_role",)
    search_fields = ("ticket__ticket_no", "body", "sender__username")
