import logging

from celery import shared_task
from django.utils import timezone

from .models import CustomUser, Notification, VIPLevel

logger = logging.getLogger(__name__)


@shared_task
def check_vip_expirations():
    expired = 0
    for user in CustomUser.objects.filter(vip_level__isnull=False).exclude(vip_level__price=0):
        if user.vip_expiry_date and timezone.now() > user.vip_expiry_date:
            free_level = VIPLevel.objects.filter(price=0).first()
            user.vip_level = free_level
            user.vip_expiry_date = None
            user.save()
            expired += 1
    logger.info(f"VIP expirations vérifiées : {expired} comptes rétrogradés")
    return expired


@shared_task
def cleanup_media_files():
    from django.conf import settings
    import os
    import shutil

    media_root = settings.MEDIA_ROOT
    count = 0
    for root, dirs, files in os.walk(media_root):
        for f in files:
            path = os.path.join(root, f)
            age = timezone.now() - timezone.datetime.fromtimestamp(
                os.path.getmtime(path), tz=timezone.get_current_timezone()
            )
            if age.days > 15:
                os.remove(path)
                count += 1
    logger.info(f"Nettoyage média : {count} fichiers supprimés")
    return count


@shared_task
def send_daily_report():
    from django.db.models import Count, Sum

    today = timezone.now().date()
    yesterday = today - timezone.timedelta(days=1)

    new_users = CustomUser.objects.filter(date_joined__date=yesterday).count()
    total_users = CustomUser.objects.count()

    logger.info(
        f"Rapport quotidien - "
        f"Nouveaux utilisateurs: {new_users}, "
        f"Total: {total_users}"
    )
    return {'new_users': new_users, 'total_users': total_users}


@shared_task
def detect_fraud():
    from django.db.models import Count
    from .models import UserTaskCompletion

    suspicious = CustomUser.objects.values('device_fingerprint') \
        .annotate(count=Count('id')) \
        .filter(count__gt=2, device_fingerprint__isnull=False)

    for entry in suspicious:
        logger.warning(
            f"Appareil suspect (fingerprint): {entry['device_fingerprint']} "
            f"→ {entry['count']} comptes"
        )

    same_ip = CustomUser.objects.values('registration_ip') \
        .annotate(count=Count('id')) \
        .filter(count__gt=2, registration_ip__isnull=False)

    for entry in same_ip:
        logger.warning(
            f"IP suspecte: {entry['registration_ip']} "
            f"→ {entry['count']} comptes"
        )

    return {'suspicious_devices': len(suspicious), 'suspicious_ips': len(same_ip)}


@shared_task
def remind_inactive_users():
    from django.db.models import Q

    threshold = timezone.now() - timezone.timedelta(days=7)
    inactive = CustomUser.objects.filter(
        Q(last_login__lt=threshold) | Q(last_login__isnull=True),
        is_active=True,
        date_joined__lt=threshold,
    )

    count = 0
    for user in inactive[:100]:
        Notification.objects.create(
            user=user,
            title="Ça fait longtemps !",
            message="Reviens miner, des nouvelles tâches t'attendent !"
        )
        count += 1

    logger.info(f"Rappel envoyé à {count} utilisateurs inactifs")
    return count


@shared_task
def send_push_badge_unlocked(user_id, badge_name):
    from .models import CustomUser
    from .utils import send_push_notification

    user = CustomUser.objects.get(id=user_id)
    send_push_notification(
        user,
        "Badge débloqué ! 🏆",
        f"Tu viens de débloquer le badge : {badge_name}",
        url='/gamification/',
    )


@shared_task
def send_push_mission_complete(user_id, mission_name, reward):
    from .models import CustomUser
    from .utils import send_push_notification

    user = CustomUser.objects.get(id=user_id)
    send_push_notification(
        user,
        "Mission accomplie ! ✅",
        f"Mission '{mission_name}' terminée — +{reward} FCFA",
        url='/gamification/',
    )


@shared_task
def send_push_mining_complete(user_id, amount):
    from .models import CustomUser
    from .utils import send_push_notification

    user = CustomUser.objects.get(id=user_id)
    send_push_notification(
        user,
        "Minage terminé ! ⛏️",
        f"Ton minage est prêt — réclame {amount} FCFA maintenant !",
        url='/dashboard/',
    )
