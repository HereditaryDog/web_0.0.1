from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


def _to_decimal(value):
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


@register.filter
def cny(value):
    amount = _to_decimal(value)
    if amount is None:
        return value
    return f"\u00a5{amount:.2f}"


@register.filter
def usd(value):
    amount = _to_decimal(value)
    if amount is None:
        return value
    return f"US${amount:.2f}"
