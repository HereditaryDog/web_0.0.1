from django import forms

from .models import CardCode, Order, Product


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(label="购买数量", min_value=1, max_value=20, initial=1)


class GuestOrderLookupForm(forms.Form):
    order_no = forms.CharField(label="订单号", max_length=32)
    email = forms.EmailField(label="下单邮箱")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category",
            "title",
            "slug",
            "summary",
            "description",
            "cover_url",
            "face_value",
            "token_amount",
            "price",
            "delivery_method",
            "provider_sku",
            "badge",
            "low_stock_threshold",
            "is_active",
            "is_featured",
        ]
        labels = {
            "category": "商品分类",
            "title": "商品名称",
            "slug": "链接标识",
            "summary": "摘要",
            "description": "商品详情",
            "cover_url": "封面图链接",
            "face_value": "面值",
            "token_amount": "Token 数量",
            "price": "售价",
            "delivery_method": "供货方式",
            "provider_sku": "合作方 SKU",
            "badge": "角标文案",
            "low_stock_threshold": "低库存提醒阈值",
            "is_active": "是否上架",
            "is_featured": "是否推荐",
        }
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }

        help_texts = {
            "low_stock_threshold": "库存卡密商品低于这个数量时会出现在后台提醒中，填 0 表示不提醒。",
        }


class MerchantOrderFilterForm(forms.Form):
    query = forms.CharField(label="搜索", required=False, max_length=120)
    status = forms.ChoiceField(label="订单状态", required=False)
    payment_status = forms.ChoiceField(label="支付状态", required=False)
    date_from = forms.DateField(label="开始日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="结束日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["query"].widget.attrs.update({"placeholder": "订单号 / 用户名 / 邮箱"})
        self.fields["status"].choices = [("", "全部订单状态"), *Order.Status.choices]
        self.fields["payment_status"].choices = [("", "全部支付状态"), *Order.PaymentStatus.choices]


class MerchantProductFilterForm(forms.Form):
    query = forms.CharField(label="搜索", required=False, max_length=120)
    active = forms.ChoiceField(
        label="上架状态",
        required=False,
        choices=(
            ("", "全部状态"),
            ("active", "仅看上架"),
            ("inactive", "仅看下架"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["query"].widget.attrs.update({"placeholder": "商品名 / slug / SKU"})


class CardCodeBatchForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.order_by("title"),
        label="关联商品",
    )
    note = forms.CharField(label="备注", max_length=120, required=False)
    codes = forms.CharField(
        label="批量卡密",
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text="一行一个卡密，系统会自动去重。",
    )

    def clean_codes(self):
        raw_codes = self.cleaned_data["codes"]
        codes = [line.strip() for line in raw_codes.splitlines() if line.strip()]
        if not codes:
            raise forms.ValidationError("请至少输入一个卡密。")
        return codes

    def build_preview(self):
        codes = self.cleaned_data["codes"]
        seen = set()
        duplicate_in_upload = []
        unique_codes = []
        for code in codes:
            if code in seen:
                if code not in duplicate_in_upload:
                    duplicate_in_upload.append(code)
                continue
            seen.add(code)
            unique_codes.append(code)

        existing_codes = list(CardCode.objects.filter(code__in=unique_codes).values_list("code", flat=True))
        existing_code_set = set(existing_codes)
        importable_codes = [code for code in unique_codes if code not in existing_code_set]
        duplicate_samples = duplicate_in_upload + [code for code in existing_codes if code not in duplicate_in_upload]

        return {
            "total_submitted": len(codes),
            "unique_submitted": len(unique_codes),
            "duplicate_in_upload": duplicate_in_upload,
            "existing_duplicates": existing_codes,
            "importable_codes": importable_codes,
            "importable_count": len(importable_codes),
            "duplicate_count": len(duplicate_in_upload) + len(existing_codes),
            "duplicate_samples": duplicate_samples[:12],
        }
