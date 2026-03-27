from django.utils import timezone
from .models import VIPLevel, Notification

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
