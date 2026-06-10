from django.contrib import admin
from django.shortcuts import render
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def handler404(request, exception):
    return render(request, 'core/404.html', status=404)

def handler403(request, exception):
    return render(request, 'core/403.html', status=403)

def handler500(request):
    return render(request, 'core/500.html', status=500)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/v1/', include('core.api_urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
        *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    ]
