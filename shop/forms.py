from django import forms

from .models import CardCode, Product


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
            "is_active": "是否上架",
            "is_featured": "是否推荐",
        }
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }


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
        if len(codes) != len(set(codes)):
            raise forms.ValidationError("本次导入中存在重复卡密，请检查。")
        existing = set(CardCode.objects.filter(code__in=codes).values_list("code", flat=True))
        if existing:
            raise forms.ValidationError(f"以下卡密已存在：{', '.join(sorted(existing)[:5])}")
        return codes
