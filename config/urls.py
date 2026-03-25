from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', RedirectView.as_view(pattern_name='accounts:login', permanent=False)),
    path('merchant/login/', RedirectView.as_view(pattern_name='accounts:merchant_login', permanent=False)),
    path('dashboard/login/', RedirectView.as_view(pattern_name='accounts:merchant_login', permanent=False)),
    path('signup/', RedirectView.as_view(pattern_name='accounts:signup', permanent=False)),
    path('forgot-password/', RedirectView.as_view(pattern_name='password_reset', permanent=False)),
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('accounts/', include('accounts.auth_urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include(('shop.urls', 'shop'), namespace='shop')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
