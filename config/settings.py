import os
from pathlib import Path

from dotenv import load_dotenv

from .version import VERSION

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]
ADMIN_ALLOWED_IPS = [ip.strip() for ip in os.getenv("ADMIN_ALLOWED_IPS", "").split(",") if ip.strip()]
MERCHANT_ALLOWED_IPS = [ip.strip() for ip in os.getenv("MERCHANT_ALLOWED_IPS", "").split(",") if ip.strip()]
TRUSTED_PROXY_IPS = [ip.strip() for ip in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if ip.strip()]

SITE_NAME = os.getenv("SITE_NAME", "G-MasterToken")
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "").strip().rstrip("/")
CARD_SECRET_KEY = os.getenv("CARD_SECRET_KEY", "").strip()
PROJECT_VERSION = os.getenv("PROJECT_VERSION", VERSION)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "cny").strip().lower() or "cny"
PAYMENT_ENABLE_MOCK_GATEWAY = os.getenv("PAYMENT_ENABLE_MOCK_GATEWAY", "true").lower() == "true"
PAYMENT_ENABLE_STRIPE_GATEWAY = os.getenv("PAYMENT_ENABLE_STRIPE_GATEWAY", "true").lower() == "true"
PAYMENT_ENABLE_ALIPAY_GATEWAY = os.getenv("PAYMENT_ENABLE_ALIPAY_GATEWAY", "false").lower() == "true"
PAYMENT_ENABLE_WECHAT_GATEWAY = os.getenv("PAYMENT_ENABLE_WECHAT_GATEWAY", "false").lower() == "true"
PAYMENT_ENABLE_USDT_GATEWAY = os.getenv("PAYMENT_ENABLE_USDT_GATEWAY", "false").lower() == "true"
PAYMENT_ENABLE_BANK_GATEWAY = os.getenv("PAYMENT_ENABLE_BANK_GATEWAY", "false").lower() == "true"
ALIPAY_APP_ID = os.getenv("ALIPAY_APP_ID", "")
ALIPAY_GATEWAY_URL = os.getenv("ALIPAY_GATEWAY_URL", "")
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "")
WECHAT_MCH_ID = os.getenv("WECHAT_MCH_ID", "")
WECHAT_API_V3_KEY = os.getenv("WECHAT_API_V3_KEY", "")
WECHAT_CERT_SERIAL_NO = os.getenv("WECHAT_CERT_SERIAL_NO", "")
USDT_NETWORK = os.getenv("USDT_NETWORK", "TRC20")
USDT_RECEIVE_ADDRESS = os.getenv("USDT_RECEIVE_ADDRESS", "")
BANK_ACCOUNT_NAME = os.getenv("BANK_ACCOUNT_NAME", "")
BANK_NAME = os.getenv("BANK_NAME", "")
BANK_ACCOUNT_NUMBER = os.getenv("BANK_ACCOUNT_NUMBER", "")
BANK_SWIFT_CODE = os.getenv("BANK_SWIFT_CODE", "")
PARTNER_API_BASE_URL = os.getenv("PARTNER_API_BASE_URL", "")
PARTNER_API_KEY = os.getenv("PARTNER_API_KEY", "")
PARTNER_TIMEOUT = int(os.getenv("PARTNER_TIMEOUT", "20"))
USE_POSTGRES = os.getenv("DATABASE_ENGINE", "sqlite").lower() in {"postgres", "postgresql"}
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "false").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("DJANGO_SESSION_COOKIE_SECURE", "false").lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("DJANGO_CSRF_COOKIE_SECURE", "false").lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("DJANGO_SECURE_HSTS_PRELOAD", "false").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'shop',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'shop.middleware.SensitiveAreaIPAllowlistMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shop.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


if USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv("DATABASE_NAME", "web_store"),
            'USER': os.getenv("DATABASE_USER", "postgres"),
            'PASSWORD': os.getenv("DATABASE_PASSWORD", ""),
            'HOST': os.getenv("DATABASE_HOST", "127.0.0.1"),
            'PORT': os.getenv("DATABASE_PORT", "5432"),
            'CONN_MAX_AGE': int(os.getenv("DATABASE_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = [
    'accounts.auth_backends.UsernameOrEmailBackend',
]


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Hong_Kong'

USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = True
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_REDIRECT_URL = 'shop:storefront'
LOGOUT_REDIRECT_URL = 'shop:storefront'
LOGIN_URL = 'accounts:login'
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@gmastertoken.local")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
EMAIL_CODE_EXPIRY_MINUTES = int(os.getenv("EMAIL_CODE_EXPIRY_MINUTES", "10"))
EMAIL_CODE_COOLDOWN_SECONDS = int(os.getenv("EMAIL_CODE_COOLDOWN_SECONDS", "60"))
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
