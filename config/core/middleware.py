from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from .models import VIPLevel, Notification


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.DEBUG:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "style-src 'self' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.tailwindcss.com 'unsafe-inline'; "
                "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https://upload.wikimedia.org https://ui-avatars.com; "
                "connect-src 'self' https://sentry.io; "
                "frame-src 'none'; "
                "object-src 'none'"
            )
        return response


class PhoneVerificationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Liste des URLs autorisées sans vérification
            allowed_urls = [
                reverse('verify_phone'),
                reverse('logout'),
                reverse('home'),
            ]
            
            # Si le téléphone n'est pas vérifié et qu'on n'est pas sur une URL autorisée
            if not request.user.is_phone_verified and request.path not in allowed_urls and not request.path.startswith('/admin/') and not request.path.startswith('/management/'):
                return redirect('verify_phone')

        response = self.get_response(request)
        return response

class VIPExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.vip_level:
            # Si le niveau n'est pas Gratuit et que la date d'expiration est passée
            if request.user.vip_level.price > 0 and request.user.vip_expiry_date:
                if timezone.now() > request.user.vip_expiry_date:
                    old_level_name = request.user.vip_level.name
                    free_level = VIPLevel.objects.filter(price=0).first()
                    
                    # Reset du niveau
                    request.user.vip_level = free_level
                    request.user.vip_expiry_date = None
                    request.user.save()
                    
                    # Notification à l'utilisateur
                    Notification.objects.create(
                        user=request.user,
                        title="Pack VIP expiré",
                        message=f"Votre abonnement au pack {old_level_name} est arrivé à son terme (120 jours). Vous avez été repositionné au niveau Gratuit."
                    )

        response = self.get_response(request)
        return response
