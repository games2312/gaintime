import json
import logging
from decimal import Decimal
from io import BytesIO

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from PIL import Image
from django.utils import timezone
from django.conf import settings

from .models import CustomUser, DailyMission, Notification, PushSubscription, Transaction, UserMissionProgress

logger = logging.getLogger(__name__)


def update_mission_progress(user, mission_type):
    try:
        today = timezone.now().date()
        mission = DailyMission.objects.filter(
            mission_type=mission_type, is_active=True
        ).first()
        if not mission:
            return
        progress, created = UserMissionProgress.objects.get_or_create(
            user=user, mission=mission, date=today,
            defaults={'progress': 0, 'completed': False},
        )
        if progress.completed:
            return
        progress.progress += 1
        if progress.progress >= mission.target:
            progress.completed = True
            user.balance += mission.reward
            user.total_earnings += mission.reward
            user.save()
            send_push_notification(
                user, 'Mission accomplie !',
                f"Mission '{mission.get_mission_type_display()}' terminée — +{mission.reward} FCFA",
                url='/gamification/',
            )
            logger.info(
                f"Mission accomplie: {user.username} → {mission.mission_type} +{mission.reward} FCFA"
            )
        progress.save()
    except Exception as e:
        logger.error(f"Mission progress error: {e}")


def send_push_notification(user, title, message, url=None):
    try:
        from pywebpush import webpush
    except ImportError:
        logger.warning("pywebpush not installed — push notification skipped")
        return 0

    try:
        subscriptions = PushSubscription.objects.filter(user=user)
        if not subscriptions.exists():
            return 0

        sent = 0
        for sub in subscriptions:
            try:
                payload = json.dumps({
                    'title': title,
                    'message': message,
                    'url': url or '/',
                })
                webpush(
                    subscription_info={
                        'endpoint': sub.endpoint,
                        'keys': {
                            'auth': sub.auth_key,
                            'p256dh': sub.p256dh_key,
                        },
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={
                        'sub': f'mailto:{settings.VAPID_CLAIM_EMAIL}',
                    },
                )
                sent += 1
            except Exception as e:
                if '410' in str(e) or '404' in str(e) or 'expired' in str(e).lower():
                    sub.delete()
                logger.warning(f"Push send failed for {user.username}: {e}")
        return sent
    except Exception as e:
        logger.error(f"Push notification error: {e}")
        return 0


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def compute_phash(image_file, hash_size=8):
    img = Image.open(image_file)
    img = img.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(img.getdata())
    diff = []
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * (hash_size + 1) + col
            diff.append(pixels[idx] > pixels[idx + 1])
    bits = sum(2 ** i for i, bit in enumerate(diff) if bit)
    return f'{bits:016x}'


def hamming_distance(hash1, hash2):
    if len(hash1) != len(hash2):
        return 100
    xor = int(hash1, 16) ^ int(hash2, 16)
    return bin(xor).count('1')


def validate_image_magic_bytes(uploaded_file):
    try:
        header = uploaded_file.read(16)
        uploaded_file.seek(0)
        if header[:2] == b'\xff\xd8':
            return True
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return True
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return True
        return False
    except Exception:
        return False

def notify_user_ws(user, title='', message='', url=''):
    try:
        layer = get_channel_layer()
        unread = user.notifications.filter(is_read=False).count()
        async_to_sync(layer.group_send)(
            f'notifications_user_{user.id}',
            {'type': 'notify', 'count': unread, 'title': title, 'message': message, 'url': url}
        )
    except Exception:
        pass

# --- XP / Level system ---

LEVEL_THRESHOLDS = {
    1: 0, 2: 100, 3: 300, 4: 600, 5: 1000,
    6: 1500, 7: 2100, 8: 2800, 9: 3600, 10: 4500,
    11: 5500, 12: 6600, 13: 7800, 14: 9100, 15: 10500,
    16: 12000, 17: 13600, 18: 15300, 19: 17100, 20: 19000,
}

def get_level_for_xp(xp):
    level = 1
    for lvl, needed in sorted(LEVEL_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if xp >= needed:
            level = lvl
            break
    return level

def award_xp(user, amount, reason=''):
    user.xp += amount
    new_level = get_level_for_xp(user.xp)
    leveled_up = new_level > user.level
    user.level = new_level
    user.save(update_fields=['xp', 'level'])
    if leveled_up:
        Notification.objects.create(
            user=user, title="Niveau supérieur !",
            message=f"Vous avez atteint le niveau {new_level} !"
        )
    return leveled_up

# --- Referral tier rewards ---

REFERRAL_TIERS = [
    {'level': 1, 'needed': 3, 'reward': Decimal('500')},
    {'level': 2, 'needed': 10, 'reward': Decimal('2000')},
    {'level': 3, 'needed': 25, 'reward': Decimal('5000')},
    {'level': 4, 'needed': 50, 'reward': Decimal('15000')},
    {'level': 5, 'needed': 100, 'reward': Decimal('50000')},
]

def check_referral_tiers(user):
    total = CustomUser.objects.filter(referred_by=user).count()
    user.total_referrals = total
    new_tier = 0
    for t in reversed(REFERRAL_TIERS):
        if total >= t['needed']:
            new_tier = t['level']
            break
    old_tier = user.referral_tier
    user.referral_tier = new_tier
    user.save(update_fields=['total_referrals', 'referral_tier'])
    for t in REFERRAL_TIERS:
        if t['level'] > old_tier and t['level'] <= new_tier:
            user.balance += t['reward']
            user.total_earnings += t['reward']
            user.save(update_fields=['balance', 'total_earnings'])
            Transaction.objects.create(
                user=user, amount=t['reward'], transaction_type='REFERRAL_BONUS',
                status='COMPLETED',
                description=f"Prime palier parrainage niveau {t['level']} ({t['needed']} filleuls)"
            )
            Notification.objects.create(
                user=user, title="Palier de parrainage atteint !",
                message=f"Vous avez atteint le palier {t['level']} ({t['needed']} filleuls) : +{t['reward']} F"
            )
