from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .utils import notify_user_ws


@receiver(post_save, sender=Notification)
def notification_created(sender, instance, created, **kwargs):
    if created:
        notify_user_ws(
            instance.user,
            title=instance.title,
            message=instance.message,
        )
