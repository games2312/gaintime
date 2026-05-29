from django.core.management.base import BaseCommand
from core.models import CustomUser, Transaction
from django.db.models import Count
from django.utils import timezone

class Command(BaseCommand):
    help = 'Analyse la base de données pour détecter les fraudes et multi-comptes'

    def handle(self, *args, **options):
        self.stdout.write("Analyse anti-fraude en cours...")
        
        # 1. Détection des adresses IP partagées (plus de 2 comptes)
        shared_ips = CustomUser.objects.values('last_ip').annotate(count=Count('id')).filter(count__gt=2).exclude(last_ip=None)
        
        if shared_ips:
            self.stdout.write(self.style.WARNING(f"\n[ALERTE IP] {shared_ips.count()} adresses IP suspectes détectées :"))
            for ip_info in shared_ips:
                ip = ip_info['last_ip']
                count = ip_info['count']
                users = CustomUser.objects.filter(last_ip=ip).values_list('username', flat=True)
                self.stdout.write(f" - IP {ip} : {count} comptes ({', '.join(users)})")
        else:
            self.stdout.write(self.style.SUCCESS("\nAucun abus d'IP détecté (limite de 2)."))

        # 2. Détection des numéros de retrait partagés
        shared_phones = CustomUser.objects.values('withdrawal_phone_locked').annotate(count=Count('id')).filter(count__gt=1).exclude(withdrawal_phone_locked=None).exclude(withdrawal_phone_locked='')
        
        if shared_phones:
            self.stdout.write(self.style.WARNING(f"\n[ALERTE RETRAIT] {shared_phones.count()} numéros de retrait partagés :"))
            for p_info in shared_phones:
                phone = p_info['withdrawal_phone_locked']
                count = p_info['count']
                users = CustomUser.objects.filter(withdrawal_phone_locked=phone).values_list('username', flat=True)
                self.stdout.write(f" - Numéro {phone} : utilisé par {count} comptes ({', '.join(users)})")
        else:
            self.stdout.write(self.style.SUCCESS("\nAucun partage de numéro de retrait détecté."))

        # 3. Détection de l'auto-parrainage (même IP que le parrain)
        self.stdout.write("\nVérification de l'auto-parrainage...")
        suspicious_referrals = CustomUser.objects.filter(
            referred_by__isnull=False,
            last_ip=timezone.now() # Juste pour la structure, on va filtrer dynamiquement
        )
        
        count_self_ref = 0
        for user in CustomUser.objects.filter(referred_by__isnull=False):
            if user.last_ip == user.referred_by.last_ip and user.last_ip is not None:
                self.stdout.write(self.style.NOTICE(f" - Soupçon d'auto-parrainage : {user.username} parrainé par {user.referred_by.username} (Même IP: {user.last_ip})"))
                count_self_ref += 1
        
        if count_self_ref == 0:
            self.stdout.write(self.style.SUCCESS("Aucun auto-parrainage direct détecté."))
        else:
            self.stdout.write(self.style.WARNING(f"Total auto-parrainage : {count_self_ref} cas."))

        self.stdout.write(self.style.SUCCESS("\nAnalyse terminée."))
