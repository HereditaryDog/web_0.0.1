from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import AddToCartForm, CardCodeBatchForm, GuestOrderLookupForm, ProductForm
from .models import (
    CardCode,
    HelpArticle,
    Order,
    PaymentAttempt,
    Product,
    ProductCategory,
    SiteAnnouncement,
)
from .services.order_flow import create_single_item_order, mark_order_paid
from .services.payment import create_checkout_session, verify_stripe_checkout


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


class StartPaymentView(LoginRequiredMixin, View):
    def post(self, request, order_no):
        order = get_object_or_404(Order, order_no=order_no, user=request.user)
        if order.payment_status == Order.PaymentStatus.PAID:
            messages.info(request, "该订单已经支付完成。")
            return redirect("shop:order_detail", order_no=order.order_no)

        session = create_checkout_session(order, request)
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
            checkout_data = verify_stripe_checkout(session_id)
            if checkout_data and checkout_data.get("payment_status") == "paid":
                mark_order_paid(order, provider="stripe", reference=session_id, payload=checkout_data)
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["orders"] = self.request.user.orders.prefetch_related("items").all()
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
            if product.delivery_method == Product.DeliveryMethod.STOCK_CARD and (product.inventory_count or 0) <= 3
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

    def get_queryset(self):
        return Product.objects.select_related("category").all().order_by("-is_active", "-is_featured", "price")


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

    def form_valid(self, form):
        product = form.cleaned_data["product"]
        note = form.cleaned_data["note"]
        codes = form.cleaned_data["codes"]
        CardCode.objects.bulk_create(
            [CardCode(product=product, code=code, note=note) for code in codes],
            batch_size=100,
        )
        messages.success(self.request, f"已导入 {len(codes)} 条卡密到 {product.title}。")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_id = self.request.GET.get("product")
        card_codes = CardCode.objects.select_related("product").order_by("-created_at")
        if product_id and product_id.isdigit():
            card_codes = card_codes.filter(product_id=product_id)
        context["card_codes"] = card_codes[:50]
        context["products"] = Product.objects.order_by("title")
        context["current_product_id"] = product_id or ""
        return context


class MerchantOrderListView(MerchantContextMixin, ListView):
    template_name = "shop/merchant_orders.html"
    context_object_name = "orders"
    merchant_tab = "orders"

    def get_queryset(self):
        status = self.request.GET.get("status", "").strip()
        queryset = Order.objects.select_related("user").prefetch_related("items").order_by("-created_at")
        valid_statuses = {choice[0] for choice in Order.Status.choices}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Order.Status.choices
        context["current_status"] = self.request.GET.get("status", "").strip()
        return context


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


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.headers.get("Stripe-Signature", "")
        checkout_data = verify_stripe_checkout(signature_payload=payload, signature=signature, from_webhook=True)
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
