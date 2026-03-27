from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from .security import decrypt_secret, encrypt_secret, hash_secret, is_encrypted_value, mask_secret


def generate_order_no():
    return timezone.now().strftime("OD%Y%m%d%H%M%S") + get_random_string(4).upper()


def generate_support_ticket_no():
    return timezone.now().strftime("CS%Y%m%d%H%M%S") + get_random_string(4).upper()


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class ProductCategory(TimeStampedModel):
    name = models.CharField("分类名称", max_length=80, unique=True)
    slug = models.SlugField("分类标识", unique=True)
    summary = models.CharField("分类说明", max_length=180, blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用中", default=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name = "商品分类"
        verbose_name_plural = "商品分类"

    def __str__(self):
        return self.name


class SiteAnnouncement(TimeStampedModel):
    title = models.CharField("公告标题", max_length=120)
    body = models.TextField("公告内容")
    link_url = models.URLField("跳转链接", blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用中", default=True)
    is_pinned = models.BooleanField("置顶", default=False)

    class Meta:
        ordering = ("-is_pinned", "sort_order", "-created_at")
        verbose_name = "站点公告"
        verbose_name_plural = "站点公告"

    def __str__(self):
        return self.title


class HelpArticle(TimeStampedModel):
    class Section(models.TextChoices):
        GUIDE = "guide", "新手教程"
        FAQ = "faq", "常见问题"
        AFTERSALE = "aftersale", "售后说明"
        API = "api", "接口对接"

    title = models.CharField("文章标题", max_length=140)
    slug = models.SlugField("文章标识", unique=True)
    section = models.CharField("文章栏目", max_length=20, choices=Section.choices, default=Section.GUIDE)
    summary = models.CharField("文章摘要", max_length=200)
    content = models.TextField("正文内容")
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_published = models.BooleanField("已发布", default=True)
    is_featured = models.BooleanField("首页展示", default=False)

    class Meta:
        ordering = ("section", "sort_order", "-created_at")
        verbose_name = "帮助文章"
        verbose_name_plural = "帮助文章"

    def __str__(self):
        return self.title


class Product(TimeStampedModel):
    class DeliveryMethod(models.TextChoices):
        STOCK_CARD = "stock_card", "库存卡密"
        PARTNER_API = "partner_api", "合作 API"

    category = models.ForeignKey(
        ProductCategory,
        related_name="products",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="商品分类",
    )
    title = models.CharField("商品名称", max_length=120)
    slug = models.SlugField("链接标识", unique=True)
    summary = models.CharField("摘要", max_length=180)
    description = models.TextField("商品详情")
    cover_url = models.URLField("封面图链接", blank=True)
    face_value = models.DecimalField("面值", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    token_amount = models.PositiveIntegerField("Token 数量", default=0)
    price = models.DecimalField("售价", max_digits=10, decimal_places=2)
    delivery_method = models.CharField(
        "供货方式",
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.STOCK_CARD,
    )
    provider_sku = models.CharField("合作方 SKU", max_length=80, blank=True)
    badge = models.CharField("角标文案", max_length=40, blank=True)
    low_stock_threshold = models.PositiveIntegerField("低库存提醒阈值", default=3)
    is_active = models.BooleanField("上架中", default=True)
    is_featured = models.BooleanField("首页推荐", default=True)

    class Meta:
        ordering = ("-is_featured", "price")
        verbose_name = "商品"
        verbose_name_plural = "商品"

    def __str__(self):
        return self.title

    @property
    def inventory_count(self):
        if self.delivery_method == self.DeliveryMethod.PARTNER_API:
            return None
        return self.card_codes.filter(status=CardCode.Status.AVAILABLE).count()

    @property
    def inventory_label(self):
        if self.delivery_method == self.DeliveryMethod.PARTNER_API:
            return "API 自动供货"
        return f"{self.inventory_count} 张可售"


class CardCode(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "可售"
        SOLD = "sold", "已售"

    product = models.ForeignKey(Product, related_name="card_codes", on_delete=models.CASCADE)
    code = models.TextField("卡密密文")
    code_hash = models.CharField("卡密哈希", max_length=64, unique=True, db_index=True, editable=False, null=True, blank=True)
    note = models.CharField("备注", max_length=120, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    sold_at = models.DateTimeField("售出时间", null=True, blank=True)

    class Meta:
        ordering = ("product", "status", "-created_at")
        verbose_name = "卡密库存"
        verbose_name_plural = "卡密库存"

    @staticmethod
    def build_code_hash(code):
        return hash_secret(code)

    def set_plaintext_code(self, code):
        self.code_hash = self.build_code_hash(code)
        self.code = encrypt_secret(code)

    def reveal_code(self):
        return decrypt_secret(self.code)

    @property
    def masked_code(self):
        return mask_secret(self.reveal_code())

    def save(self, *args, **kwargs):
        if self.code:
            plain_code = self.code if not is_encrypted_value(self.code) else decrypt_secret(self.code)
            self.set_plaintext_code(plain_code)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.title} - {self.masked_code}"


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "待支付"
        PAID = "paid", "已支付"
        FULFILLING = "fulfilling", "发货中"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失败"
        CANCELLED = "cancelled", "已取消"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "未支付"
        CHECKOUT_CREATED = "checkout_created", "支付链接已创建"
        PAID = "paid", "支付成功"
        REFUNDED = "refunded", "已退款"

    order_no = models.CharField("订单号", max_length=32, unique=True, default=generate_order_no)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.CASCADE)
    contact_email = models.EmailField("查询邮箱", blank=True)
    status = models.CharField("订单状态", max_length=30, choices=Status.choices, default=Status.PENDING_PAYMENT)
    payment_status = models.CharField(
        "支付状态",
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    payment_provider = models.CharField("支付渠道", max_length=40, blank=True)
    payment_reference = models.CharField("支付流水", max_length=120, blank=True)
    checkout_url = models.URLField("支付链接", blank=True, max_length=2048)
    customer_note = models.CharField("买家备注", max_length=240, blank=True)
    merchant_note = models.CharField("商家备注", max_length=240, blank=True)
    subtotal = models.DecimalField("小计", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField("应付金额", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    paid_at = models.DateTimeField("支付时间", null=True, blank=True)
    fulfilled_at = models.DateTimeField("发货时间", null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "订单"
        verbose_name_plural = "订单"

    def __str__(self):
        return self.order_no

    def sync_totals(self):
        subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        self.subtotal = subtotal
        self.total_amount = subtotal
        return subtotal


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    product_title = models.CharField("下单商品名", max_length=120)
    quantity = models.PositiveIntegerField("数量", default=1)
    unit_price = models.DecimalField("单价", max_digits=10, decimal_places=2)
    line_total = models.DecimalField("行金额", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "订单明细"
        verbose_name_plural = "订单明细"

    def __str__(self):
        return f"{self.order.order_no} - {self.product_title}"


class DeliveryRecord(TimeStampedModel):
    class Source(models.TextChoices):
        STOCK = "stock", "库存卡密"
        API = "api", "合作 API"

    order_item = models.ForeignKey(OrderItem, related_name="deliveries", on_delete=models.CASCADE)
    source = models.CharField("来源", max_length=20, choices=Source.choices)
    display_code = models.TextField("交付密文")
    supplier_payload = models.JSONField("供应商返回", default=dict, blank=True)
    delivered_at = models.DateTimeField("交付时间", auto_now_add=True)

    class Meta:
        verbose_name = "发货记录"
        verbose_name_plural = "发货记录"

    def reveal_display_code(self):
        return decrypt_secret(self.display_code)

    @property
    def masked_display_code(self):
        return mask_secret(self.reveal_display_code())

    def save(self, *args, **kwargs):
        if self.display_code:
            self.display_code = encrypt_secret(self.display_code)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_item.order.order_no} - {self.masked_display_code}"


class PaymentAttempt(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = "created", "已创建"
        PAID = "paid", "已支付"
        FAILED = "failed", "失败"

    order = models.ForeignKey(Order, related_name="payment_attempts", on_delete=models.CASCADE)
    provider = models.CharField("支付平台", max_length=40)
    reference = models.CharField("平台流水", max_length=120)
    checkout_url = models.URLField("支付跳转", blank=True, max_length=2048)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.CREATED)
    raw_payload = models.JSONField("原始数据", default=dict, blank=True)

    class Meta:
        verbose_name = "支付记录"
        verbose_name_plural = "支付记录"

    def __str__(self):
        return f"{self.order.order_no} - {self.provider}"


class InventoryImportBatch(TimeStampedModel):
    product = models.ForeignKey(Product, related_name="import_batches", on_delete=models.CASCADE)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="inventory_import_batches",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.CharField("备注", max_length=120, blank=True)
    total_submitted = models.PositiveIntegerField("提交数量", default=0)
    imported_count = models.PositiveIntegerField("成功导入", default=0)
    duplicate_count = models.PositiveIntegerField("重复数量", default=0)
    duplicate_sample = models.TextField("重复样例", blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "库存导入批次"
        verbose_name_plural = "库存导入批次"

    def __str__(self):
        return f"{self.product.title} - {self.created_at:%Y-%m-%d %H:%M:%S}"


class SensitiveOperationLog(TimeStampedModel):
    class Action(models.TextChoices):
        REVEAL_CARD_CODE = "reveal_card_code", "查看库存卡密"
        REVEAL_DELIVERY_CODE = "reveal_delivery_code", "查看发货内容"
        SEND_DELIVERY_REMINDER = "send_delivery_reminder", "发送查看提醒"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="sensitive_operation_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField("操作类型", max_length=40, choices=Action.choices)
    order = models.ForeignKey("Order", related_name="sensitive_logs", on_delete=models.SET_NULL, null=True, blank=True)
    card_code = models.ForeignKey("CardCode", related_name="sensitive_logs", on_delete=models.SET_NULL, null=True, blank=True)
    delivery_record = models.ForeignKey(
        "DeliveryRecord",
        related_name="sensitive_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField("来源 IP", null=True, blank=True)
    note = models.CharField("备注", max_length=240, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "敏感操作日志"
        verbose_name_plural = "敏感操作日志"

    def __str__(self):
        return f"{self.action} - {self.created_at:%Y-%m-%d %H:%M:%S}"


class SupportTicket(TimeStampedModel):
    class Category(models.TextChoices):
        ORDER = "order", "订单问题"
        DELIVERY = "delivery", "发货问题"
        PAYMENT = "payment", "支付问题"
        ACCOUNT = "account", "账号问题"
        API = "api", "接口问题"
        AFTERSALE = "aftersale", "售后处理"
        OTHER = "other", "其他"

    class Status(models.TextChoices):
        PENDING_SUPPORT = "pending_support", "待客服处理"
        PENDING_USER = "pending_user", "待用户回复"
        RESOLVED = "resolved", "已解决"
        CLOSED = "closed", "已关闭"

    class Priority(models.TextChoices):
        LOW = "low", "低"
        NORMAL = "normal", "普通"
        HIGH = "high", "高"

    ticket_no = models.CharField("工单号", max_length=32, unique=True, default=generate_support_ticket_no)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="support_tickets",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    order = models.ForeignKey("Order", related_name="support_tickets", on_delete=models.SET_NULL, null=True, blank=True)
    contact_email = models.EmailField("联系邮箱")
    category = models.CharField("工单分类", max_length=20, choices=Category.choices, default=Category.ORDER)
    priority = models.CharField("优先级", max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    subject = models.CharField("工单标题", max_length=160)
    status = models.CharField("工单状态", max_length=20, choices=Status.choices, default=Status.PENDING_SUPPORT)
    merchant_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_support_tickets",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    last_message_at = models.DateTimeField("最后消息时间", default=timezone.now)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)

    class Meta:
        ordering = ("-last_message_at", "-created_at")
        verbose_name = "客服工单"
        verbose_name_plural = "客服工单"

    def __str__(self):
        return self.ticket_no


class SupportTicketMessage(TimeStampedModel):
    class SenderRole(models.TextChoices):
        USER = "user", "用户"
        SUPPORT = "support", "客服"
        SYSTEM = "system", "系统"

    ticket = models.ForeignKey(SupportTicket, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="support_ticket_messages",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sender_role = models.CharField("发送方角色", max_length=20, choices=SenderRole.choices)
    body = models.TextField("消息内容")

    class Meta:
        ordering = ("created_at",)
        verbose_name = "工单消息"
        verbose_name_plural = "工单消息"

    def __str__(self):
        return f"{self.ticket.ticket_no} - {self.sender_role}"
