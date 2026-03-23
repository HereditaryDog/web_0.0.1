from decimal import Decimal

from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    AddToCartForm,
    CardCodeBatchForm,
    GuestOrderLookupForm,
    MerchantOrderFilterForm,
    MerchantProductFilterForm,
    ProductForm,
)
from .models import (
    CardCode,
    HelpArticle,
    InventoryImportBatch,
    Order,
    PaymentAttempt,
    Product,
    ProductCategory,
    SiteAnnouncement,
)
from .services.order_flow import create_single_item_order, mark_order_paid
from .services.payment import (
    create_checkout_session,
    get_default_gateway_code,
    list_active_payment_gateways,
    list_reserved_payment_gateways,
    verify_payment_callback,
)


def collect_delivery_codes(order):
    return [delivery.display_code for item in order.items.all() for delivery in item.deliveries.all()]


def send_delivery_codes_email(order):
    delivery_codes = collect_delivery_codes(order)
    recipient = order.contact_email or order.user.email
    if not recipient:
        raise ValueError("当前订单没有可用的收件邮箱。")
    if not delivery_codes:
        raise ValueError("当前订单还没有可重发的发货内容。")

    content_lines = [
        f"订单号：{order.order_no}",
        f"用户：{order.user.username}",
        "",
        "以下是当前订单的发货内容：",
        *delivery_codes,
        "",
        "如果你已收到，可忽略这封邮件。",
        settings.SITE_NAME,
    ]
    send_mail(
        subject=f"{settings.SITE_NAME} 订单发货内容重发 - {order.order_no}",
        message="\n".join(content_lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )
    return recipient, len(delivery_codes)


class MerchantRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_staff or user.is_superuser or user.is_merchant)


class MerchantContextMixin(MerchantRequiredMixin):
    merchant_tab = "dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["merchant_tab"] = self.merchant_tab
        return context


class StorefrontView(ListView):
    template_name = "shop/storefront.html"
    context_object_name = "products"

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related("category")
        keyword = self.request.GET.get("q", "").strip()
        category_slug = self.request.GET.get("category", "").strip()
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword)
                | Q(summary__icontains=keyword)
                | Q(description__icontains=keyword)
            )
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset.order_by("-is_featured", "price")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = ProductCategory.objects.filter(is_active=True).annotate(
            active_product_count=Count("products", filter=Q(products__is_active=True))
        )
        context["announcements"] = SiteAnnouncement.objects.filter(is_active=True)[:5]
        context["featured_articles"] = HelpArticle.objects.filter(is_published=True, is_featured=True)[:4]
        context["current_category"] = self.request.GET.get("category", "").strip()
        context["keyword"] = self.request.GET.get("q", "").strip()
        context["lookup_form"] = GuestOrderLookupForm()
        return context


class ProductDetailView(DetailView):
    template_name = "shop/product_detail.html"
    model = Product
    context_object_name = "product"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = AddToCartForm()
        return context


class CreateOrderView(LoginRequiredMixin, View):
    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug, is_active=True)
        form = AddToCartForm(request.POST)
        if not form.is_valid():
            messages.error(request, "购买数量不合法，请重新提交。")
            return redirect("shop:product_detail", slug=slug)

        order = create_single_item_order(request.user, product, form.cleaned_data["quantity"])
        messages.success(request, f"订单 {order.order_no} 已创建，请继续支付。")
        return redirect("shop:checkout", order_no=order.order_no)


class CheckoutView(LoginRequiredMixin, DetailView):
    template_name = "shop/checkout.html"
    context_object_name = "order"
    slug_field = "order_no"
    slug_url_kwarg = "order_no"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items__deliveries")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payment_gateways"] = list_active_payment_gateways()
        context["reserved_payment_gateways"] = list_reserved_payment_gateways()
        context["default_payment_gateway"] = get_default_gateway_code()
        return context


class StartPaymentView(LoginRequiredMixin, View):
    def post(self, request, order_no):
        order = get_object_or_404(Order, order_no=order_no, user=request.user)
        if order.payment_status == Order.PaymentStatus.PAID:
            messages.info(request, "该订单已经支付完成。")
            return redirect("shop:order_detail", order_no=order.order_no)

        provider_code = request.POST.get("provider", "").strip()
        try:
            session = create_checkout_session(order, request, provider_code=provider_code)
        except ValueError:
            messages.error(request, "当前选择的支付通道尚未启用，请更换其它支付方式。")
            return redirect("shop:checkout", order_no=order.order_no)

        order.payment_provider = session.provider
        order.payment_reference = session.reference
        order.checkout_url = session.redirect_url
        order.payment_status = Order.PaymentStatus.CHECKOUT_CREATED
        order.save(
            update_fields=[
                "payment_provider",
                "payment_reference",
                "checkout_url",
                "payment_status",
                "updated_at",
            ]
        )

        PaymentAttempt.objects.create(
            order=order,
            provider=session.provider,
            reference=session.reference,
            checkout_url=session.redirect_url,
            raw_payload=session.raw_payload,
        )
        return redirect(session.redirect_url)


class MockPaymentView(LoginRequiredMixin, TemplateView):
    template_name = "shop/mock_pay.html"

    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(Order, order_no=kwargs["order_no"], user=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["order"] = self.order
        return context

    def post(self, request, *args, **kwargs):
        if self.order.payment_status != Order.PaymentStatus.PAID:
            mark_order_paid(
                self.order,
                provider="mock",
                reference=f"mock-{self.order.order_no}",
                payload={"mode": "local-demo"},
            )
            messages.success(request, "模拟支付成功，订单已经自动发货。")
        return redirect("shop:order_detail", order_no=self.order.order_no)


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    template_name = "shop/payment_result.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = get_object_or_404(Order, order_no=kwargs["order_no"], user=self.request.user)
        session_id = self.request.GET.get("session_id", "")
        if order.payment_status != Order.PaymentStatus.PAID and session_id:
            checkout_data = verify_payment_callback(order.payment_provider, session_id=session_id)
            if checkout_data and checkout_data.get("payment_status") == "paid":
                mark_order_paid(order, provider=order.payment_provider, reference=session_id, payload=checkout_data)
        context["order"] = order
        context["result_title"] = "支付结果"
        context["result_message"] = "如果订单已经付款，系统会在几秒内完成自动发货。"
        return context


class PaymentCancelView(LoginRequiredMixin, TemplateView):
    template_name = "shop/payment_result.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["order"] = get_object_or_404(Order, order_no=kwargs["order_no"], user=self.request.user)
        context["result_title"] = "支付已取消"
        context["result_message"] = "订单仍然保留，你可以稍后继续支付。"
        return context


class OrderDetailView(LoginRequiredMixin, DetailView):
    template_name = "shop/order_detail.html"
    context_object_name = "order"
    slug_field = "order_no"
    slug_url_kwarg = "order_no"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items__deliveries")


class GuestOrderLookupView(FormView):
    template_name = "shop/order_lookup.html"
    form_class = GuestOrderLookupForm
    success_url = reverse_lazy("shop:order_lookup")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["order"] = kwargs.get("order")
        return context

    def form_valid(self, form):
        order_no = form.cleaned_data["order_no"].strip()
        email = form.cleaned_data["email"].strip().lower()
        order = (
            Order.objects.select_related("user")
            .prefetch_related("items__deliveries")
            .filter(order_no=order_no)
            .filter(Q(contact_email__iexact=email) | Q(user__email__iexact=email))
            .first()
        )
        if not order:
            form.add_error(None, "没有找到匹配的订单，请检查订单号和邮箱。")
            return self.form_invalid(form)
        return self.render_to_response(self.get_context_data(form=form, order=order))


class SupportView(TemplateView):
    template_name = "shop/support.html"


class AnnouncementDetailView(DetailView):
    template_name = "shop/announcement_detail.html"
    model = SiteAnnouncement
    context_object_name = "announcement"

    def get_queryset(self):
        return SiteAnnouncement.objects.filter(is_active=True)


class HelpCenterView(ListView):
    template_name = "shop/help_center.html"
    context_object_name = "articles"

    def get_queryset(self):
        queryset = HelpArticle.objects.filter(is_published=True)
        section = self.request.GET.get("section", "").strip()
        valid_sections = {choice[0] for choice in HelpArticle.Section.choices}
        if section in valid_sections:
            queryset = queryset.filter(section=section)
        return queryset.order_by("section", "sort_order", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section_choices"] = HelpArticle.Section.choices
        context["current_section"] = self.request.GET.get("section", "").strip()
        context["featured_articles"] = HelpArticle.objects.filter(is_published=True, is_featured=True)[:5]
        return context


class HelpArticleDetailView(DetailView):
    template_name = "shop/help_article_detail.html"
    model = HelpArticle
    context_object_name = "article"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return HelpArticle.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["related_articles"] = (
            HelpArticle.objects.filter(is_published=True, section=self.object.section)
            .exclude(pk=self.object.pk)
            .order_by("sort_order", "-created_at")[:6]
        )
        return context


class AccountCenterView(LoginRequiredMixin, TemplateView):
    template_name = "shop/account_center.html"

    def get_filtered_orders(self):
        queryset = (
            self.request.user.orders.select_related("user")
            .prefetch_related("items__product", "items__deliveries")
            .order_by("-created_at")
        )
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        payment_status = self.request.GET.get("payment_status", "").strip()
        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()
        if query:
            queryset = queryset.filter(
                Q(order_no__icontains=query)
                | Q(items__product_title__icontains=query)
                | Q(payment_reference__icontains=query)
            ).distinct()
        valid_statuses = {choice[0] for choice in Order.Status.choices}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)
        valid_payment_statuses = {choice[0] for choice in Order.PaymentStatus.choices}
        if payment_status in valid_payment_statuses:
            queryset = queryset.filter(payment_status=payment_status)
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["orders"] = self.get_filtered_orders()
        context["status_choices"] = Order.Status.choices
        context["payment_status_choices"] = Order.PaymentStatus.choices
        context["current_query"] = self.request.GET.get("q", "").strip()
        context["current_status"] = self.request.GET.get("status", "").strip()
        context["current_payment_status"] = self.request.GET.get("payment_status", "").strip()
        context["current_date_from"] = self.request.GET.get("date_from", "").strip()
        context["current_date_to"] = self.request.GET.get("date_to", "").strip()
        return context


class MerchantDashboardView(MerchantContextMixin, TemplateView):
    template_name = "shop/merchant_dashboard.html"
    merchant_tab = "dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders = Order.objects.prefetch_related("items", "user")
        products = Product.objects.select_related("category").all()
        low_stock_products = [
            product
            for product in products
            if (
                product.delivery_method == Product.DeliveryMethod.STOCK_CARD
                and product.low_stock_threshold > 0
                and (product.inventory_count or 0) <= product.low_stock_threshold
            )
        ]
        context.update(
            {
                "recent_orders": orders[:8],
                "product_count": products.count(),
                "category_count": ProductCategory.objects.filter(is_active=True).count(),
                "article_count": HelpArticle.objects.filter(is_published=True).count(),
                "paid_order_count": orders.filter(payment_status=Order.PaymentStatus.PAID).count(),
                "pending_order_count": orders.filter(status=Order.Status.PENDING_PAYMENT).count(),
                "card_stock_count": CardCode.objects.filter(status=CardCode.Status.AVAILABLE).count(),
                "low_stock_products": low_stock_products,
            }
        )
        return context


class MerchantProductListView(MerchantContextMixin, ListView):
    template_name = "shop/merchant_products.html"
    context_object_name = "products"
    merchant_tab = "products"

    def get_filter_form(self):
        if not hasattr(self, "_filter_form"):
            self._filter_form = MerchantProductFilterForm(self.request.GET or None)
        return self._filter_form

    def get_queryset(self):
        queryset = Product.objects.select_related("category").all().order_by("-is_active", "-is_featured", "price")
        form = self.get_filter_form()
        if form.is_valid():
            query = form.cleaned_data["query"]
            active = form.cleaned_data["active"]
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query)
                    | Q(slug__icontains=query)
                    | Q(summary__icontains=query)
                    | Q(provider_sku__icontains=query)
                )
            if active == "active":
                queryset = queryset.filter(is_active=True)
            elif active == "inactive":
                queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        return context


class MerchantProductToggleStatusView(MerchantRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        product = get_object_or_404(Product, pk=pk)
        product.is_active = not product.is_active
        product.save(update_fields=["is_active", "updated_at"])
        state_label = "上架" if product.is_active else "下架"
        messages.success(request, f"{product.title} 已切换为{state_label}状态。")
        return redirect(request.POST.get("next") or reverse("shop:merchant_products"))


class MerchantProductCreateView(MerchantContextMixin, CreateView):
    template_name = "shop/merchant_product_form.html"
    form_class = ProductForm
    success_url = reverse_lazy("shop:merchant_products")
    merchant_tab = "products"

    def form_valid(self, form):
        messages.success(self.request, "商品已创建。")
        return super().form_valid(form)


class MerchantProductUpdateView(MerchantContextMixin, UpdateView):
    template_name = "shop/merchant_product_form.html"
    form_class = ProductForm
    model = Product
    success_url = reverse_lazy("shop:merchant_products")
    merchant_tab = "products"

    def form_valid(self, form):
        messages.success(self.request, "商品已更新。")
        return super().form_valid(form)


class MerchantInventoryView(MerchantContextMixin, FormView):
    template_name = "shop/merchant_inventory.html"
    form_class = CardCodeBatchForm
    success_url = reverse_lazy("shop:merchant_inventory")
    merchant_tab = "inventory"

    def get_import_preview(self):
        return getattr(self, "import_preview", None)

    def form_valid(self, form):
        product = form.cleaned_data["product"]
        note = form.cleaned_data["note"]
        preview = form.build_preview()
        self.import_preview = preview
        intent = self.request.POST.get("intent", "import")
        if intent == "preview":
            messages.info(self.request, "已生成导入预览，请确认后再执行导入。")
            return self.render_to_response(self.get_context_data(form=form))

        codes = preview["importable_codes"]
        if not codes:
            form.add_error("codes", "没有可导入的新卡密，重复内容已在预览中列出。")
            return self.render_to_response(self.get_context_data(form=form))
        CardCode.objects.bulk_create(
            [CardCode(product=product, code=code, note=note) for code in codes],
            batch_size=100,
        )
        duplicate_sample = "\n".join(preview["duplicate_samples"])
        InventoryImportBatch.objects.create(
            product=product,
            operator=self.request.user,
            note=note,
            total_submitted=preview["total_submitted"],
            imported_count=preview["importable_count"],
            duplicate_count=preview["duplicate_count"],
            duplicate_sample=duplicate_sample,
        )
        if preview["duplicate_count"]:
            messages.warning(
                self.request,
                f"已导入 {len(codes)} 条新卡密，忽略 {preview['duplicate_count']} 条重复内容。",
            )
        else:
            messages.success(self.request, f"已导入 {len(codes)} 条卡密到 {product.title}。")
        return redirect(f"{self.success_url}?product={product.id}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_id = self.request.GET.get("product")
        card_codes = CardCode.objects.select_related("product").order_by("-created_at")
        if product_id and product_id.isdigit():
            card_codes = card_codes.filter(product_id=product_id)
        context["card_codes"] = card_codes[:50]
        context["products"] = Product.objects.order_by("title")
        context["current_product_id"] = product_id or ""
        context["import_preview"] = self.get_import_preview()
        context["import_history"] = InventoryImportBatch.objects.select_related("product", "operator")[:12]
        return context


class MerchantOrderListView(MerchantContextMixin, ListView):
    template_name = "shop/merchant_orders.html"
    context_object_name = "orders"
    merchant_tab = "orders"

    def get_filter_form(self):
        if not hasattr(self, "_filter_form"):
            self._filter_form = MerchantOrderFilterForm(self.request.GET or None)
        return self._filter_form

    def get_queryset(self):
        queryset = Order.objects.select_related("user").prefetch_related("items__deliveries").order_by("-created_at")
        form = self.get_filter_form()
        if form.is_valid():
            query = form.cleaned_data["query"]
            status = form.cleaned_data["status"]
            payment_status = form.cleaned_data["payment_status"]
            date_from = form.cleaned_data["date_from"]
            date_to = form.cleaned_data["date_to"]
            if query:
                queryset = queryset.filter(
                    Q(order_no__icontains=query)
                    | Q(user__username__icontains=query)
                    | Q(user__email__icontains=query)
                    | Q(contact_email__icontains=query)
                    | Q(payment_reference__icontains=query)
                )
            if status:
                queryset = queryset.filter(status=status)
            if payment_status:
                queryset = queryset.filter(payment_status=payment_status)
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.get_filter_form()
        return context


class MerchantOrderActionView(MerchantRequiredMixin, View):
    def post(self, request, order_no, *args, **kwargs):
        order = get_object_or_404(
            Order.objects.select_related("user").prefetch_related("items__deliveries"),
            order_no=order_no,
        )
        next_url = request.POST.get("next") or reverse("shop:merchant_order_detail", args=[order.order_no])
        action = request.POST.get("action", "").strip()

        if action == "mark_failed":
            merchant_note = request.POST.get("merchant_note", "").strip() or "商家手动标记为异常订单。"
            order.status = Order.Status.FAILED
            order.merchant_note = merchant_note
            order.save(update_fields=["status", "merchant_note", "updated_at"])
            messages.warning(request, f"订单 {order.order_no} 已标记为异常。")
        elif action == "resend_delivery":
            try:
                recipient, count = send_delivery_codes_email(order)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"已将 {count} 条发货内容重发到 {recipient}。")
        else:
            messages.error(request, "未识别的订单操作。")

        return redirect(next_url)


class MerchantOrderDetailView(MerchantContextMixin, DetailView):
    template_name = "shop/merchant_order_detail.html"
    context_object_name = "order"
    slug_field = "order_no"
    slug_url_kwarg = "order_no"
    merchant_tab = "orders"

    def get_queryset(self):
        return (
            Order.objects.select_related("user")
            .prefetch_related("items__deliveries", "payment_attempts")
            .all()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["delivery_codes"] = collect_delivery_codes(self.object)
        return context


class ReorderView(LoginRequiredMixin, View):
    def post(self, request, order_no, *args, **kwargs):
        order = get_object_or_404(
            Order.objects.prefetch_related("items__product"),
            order_no=order_no,
            user=request.user,
        )
        first_item = order.items.select_related("product").first()
        if not first_item or not first_item.product:
            messages.error(request, "原订单没有可复购的商品。")
            return redirect("shop:account_center")
        if not first_item.product.is_active:
            messages.error(request, "该商品当前已下架，暂时无法再次购买。")
            return redirect("shop:order_detail", order_no=order.order_no)

        new_order = create_single_item_order(request.user, first_item.product, first_item.quantity)
        messages.success(request, f"已根据历史订单创建新订单 {new_order.order_no}。")
        return redirect("shop:checkout", order_no=new_order.order_no)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get("Stripe-Signature", "")
        checkout_data = verify_payment_callback(
            "stripe",
            signature_payload=payload,
            signature=signature,
            from_webhook=True,
        )
        if not checkout_data:
            return HttpResponseBadRequest("invalid payload")

        if checkout_data.get("type") == "checkout.session.completed":
            session = checkout_data["data"]["object"]
            order_no = session.get("metadata", {}).get("order_no")
            if order_no:
                order = Order.objects.filter(order_no=order_no).first()
                if order and order.payment_status != Order.PaymentStatus.PAID:
                    mark_order_paid(order, provider="stripe", reference=session["id"], payload=session)
        return HttpResponse(status=200)


class HealthView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"ok": True, "service": "web_0.0.1"})
