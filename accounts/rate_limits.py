from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from shop.security import get_request_ip

from .models import SecurityThrottle


@dataclass(frozen=True)
class ThrottlePolicy:
    window_seconds: int
    max_attempts: int
    cooldown_seconds: int
    message: str


@dataclass(frozen=True)
class ThrottleDecision:
    blocked: bool
    retry_after: int
    message: str


DEFAULT_THROTTLE_POLICIES = {
    "login_ip": ThrottlePolicy(900, 10, 900, "登录失败次数过多，请稍后再试。"),
    "login_account": ThrottlePolicy(900, 5, 900, "登录失败次数过多，请稍后再试。"),
    "merchant_login_ip": ThrottlePolicy(1800, 6, 1800, "商家登录失败次数过多，请稍后再试。"),
    "merchant_login_account": ThrottlePolicy(1800, 3, 1800, "商家登录失败次数过多，请稍后再试。"),
    "signup_code_ip": ThrottlePolicy(3600, 8, 3600, "验证码请求过于频繁，请稍后再试。"),
    "signup_code_email": ThrottlePolicy(1800, 3, 1800, "验证码请求过于频繁，请稍后再试。"),
    "order_lookup_ip": ThrottlePolicy(600, 12, 900, "查询过于频繁，请稍后再试。"),
}


def get_throttle_policy(scope):
    override = getattr(settings, "SECURITY_THROTTLE_POLICIES", {}).get(scope, {})
    base = DEFAULT_THROTTLE_POLICIES[scope]
    return ThrottlePolicy(
        window_seconds=int(override.get("window_seconds", base.window_seconds)),
        max_attempts=int(override.get("max_attempts", base.max_attempts)),
        cooldown_seconds=int(override.get("cooldown_seconds", base.cooldown_seconds)),
        message=str(override.get("message", base.message)),
    )


def normalize_login_bucket(login_value):
    normalized = (login_value or "").strip().lower()
    if not normalized:
        return ""
    user_model = get_user_model()
    try:
        if "@" in normalized:
            user = user_model.objects.filter(email__iexact=normalized).only("pk").first()
        else:
            user = user_model.objects.filter(username__iexact=normalized).only("pk").first()
    except Exception:
        user = None
    if user is not None:
        return f"user:{user.pk}"
    if "@" in normalized:
        return f"email:{normalized}"
    return f"username:{normalized}"


def build_login_throttle_scopes(scope_prefix, request, login_value):
    ip_address = get_request_ip(request) if request is not None else ""
    account_bucket = normalize_login_bucket(login_value)
    scopes = []
    if ip_address:
        scopes.append((f"{scope_prefix}_ip", ip_address))
    if account_bucket:
        scopes.append((f"{scope_prefix}_account", account_bucket))
    return scopes


def build_login_success_buckets(scope_prefix, request, login_value, user=None):
    buckets = set(build_login_throttle_scopes(scope_prefix, request, login_value))
    if user is not None:
        buckets.add((f"{scope_prefix}_account", f"user:{user.pk}"))
        buckets.add((f"{scope_prefix}_account", normalize_login_bucket(user.username)))
        buckets.add((f"{scope_prefix}_account", normalize_login_bucket(user.email)))
    return [pair for pair in buckets if pair[1]]


def _normalize_record(record, policy, now):
    changed = False
    if record.blocked_until and record.blocked_until <= now:
        record.blocked_until = None
        changed = True
    if record.last_attempt_at < now - timedelta(seconds=policy.window_seconds):
        record.attempt_count = 0
        record.window_started_at = now
        changed = True
    if changed:
        record.last_attempt_at = now
        record.save(update_fields=["attempt_count", "window_started_at", "blocked_until", "last_attempt_at"])
    return record


def _get_record(scope, bucket, policy, now=None):
    now = now or timezone.now()
    record, _ = SecurityThrottle.objects.get_or_create(
        scope=scope,
        bucket=bucket,
        defaults={
            "attempt_count": 0,
            "window_started_at": now,
            "last_attempt_at": now,
        },
    )
    return _normalize_record(record, policy, now)


def get_throttle_status(scope, bucket):
    if not bucket:
        return ThrottleDecision(blocked=False, retry_after=0, message="")
    policy = get_throttle_policy(scope)
    now = timezone.now()
    record = _get_record(scope, bucket, policy, now=now)
    if record.blocked_until and record.blocked_until > now:
        retry_after = max(1, int((record.blocked_until - now).total_seconds()))
        return ThrottleDecision(blocked=True, retry_after=retry_after, message=policy.message)
    return ThrottleDecision(blocked=False, retry_after=0, message="")


def register_failure(scope, bucket):
    if not bucket:
        return ThrottleDecision(blocked=False, retry_after=0, message="")
    policy = get_throttle_policy(scope)
    now = timezone.now()
    record = _get_record(scope, bucket, policy, now=now)
    record.attempt_count += 1
    record.last_attempt_at = now
    if record.attempt_count >= policy.max_attempts:
        record.blocked_until = now + timedelta(seconds=policy.cooldown_seconds)
    record.save(update_fields=["attempt_count", "last_attempt_at", "blocked_until"])
    if record.blocked_until and record.blocked_until > now:
        retry_after = max(1, int((record.blocked_until - now).total_seconds()))
        return ThrottleDecision(blocked=True, retry_after=retry_after, message=policy.message)
    return ThrottleDecision(blocked=False, retry_after=0, message="")


def clear_throttle(scope, bucket):
    if not bucket:
        return
    SecurityThrottle.objects.filter(scope=scope, bucket=bucket).delete()


def clear_login_failures(scope_prefix, request, login_value, user=None):
    for scope, bucket in build_login_success_buckets(scope_prefix, request, login_value, user=user):
        clear_throttle(scope, bucket)


def consume_request(scope, bucket):
    if not bucket:
        return ThrottleDecision(blocked=False, retry_after=0, message="")
    policy = get_throttle_policy(scope)
    now = timezone.now()
    record = _get_record(scope, bucket, policy, now=now)
    if record.blocked_until and record.blocked_until > now:
        retry_after = max(1, int((record.blocked_until - now).total_seconds()))
        return ThrottleDecision(blocked=True, retry_after=retry_after, message=policy.message)
    record.attempt_count += 1
    record.last_attempt_at = now
    if record.attempt_count >= policy.max_attempts:
        record.blocked_until = now + timedelta(seconds=policy.cooldown_seconds)
    record.save(update_fields=["attempt_count", "last_attempt_at", "blocked_until"])
    if record.blocked_until and record.blocked_until > now:
        retry_after = max(1, int((record.blocked_until - now).total_seconds()))
        return ThrottleDecision(blocked=True, retry_after=retry_after, message=policy.message)
    return ThrottleDecision(blocked=False, retry_after=0, message="")
