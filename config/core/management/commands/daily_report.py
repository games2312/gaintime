from django.core.management.base import BaseCommand
from core.models import CustomUser, Transaction, MiningSession, UserTaskCompletion
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal

class Command(BaseCommand):
    help = 'Génère un rapport de performance des dernières 24 heures'

    def handle(self, *args, **options):
        now = timezone.now()
        yesterday = now - timezone.timedelta(days=1)
        
        self.stdout.write(self.style.MIGRATE_HEADING(f"--- RAPPORT DE PERFORMANCE (24H) ---"))
        self.stdout.write(f"Période : {yesterday.strftime('%d/%m %H:%M')} au {now.strftime('%d/%m %H:%M')}\n")

        # 1. FINANCES
        deposits = Transaction.objects.filter(
            transaction_type='DEPOSIT', status='COMPLETED', created_at__gte=yesterday
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        withdrawals = Transaction.objects.filter(
            transaction_type='WITHDRAWAL', status='COMPLETED', created_at__gte=yesterday
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        vip_sales = Transaction.objects.filter(
            transaction_type='VIP_PURCHASE', status='COMPLETED', created_at__gte=yesterday
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        self.stdout.write(self.style.SUCCESS(f"[FINANCES]"))
        self.stdout.write(f" - Dépôts validés : {deposits} FCFA")
        self.stdout.write(f" - Ventes VIP : {vip_sales} FCFA")
        self.stdout.write(f" - Retraits payés : {withdrawals} FCFA")
        self.stdout.write(f" - Bénéfice Net (Dépôts+VIP - Retraits) : {deposits + vip_sales - withdrawals} FCFA")

        # 2. ACTIVITÉ
        mining_count = MiningSession.objects.filter(start_time__gte=yesterday).count()
        tasks_count = UserTaskCompletion.objects.filter(completed_at__gte=yesterday, status='APPROVED').count()
        
        self.stdout.write(self.style.SUCCESS(f"\n[ACTIVITÉ]"))
        self.stdout.write(f" - Sessions de minage lancées : {mining_count}")
        self.stdout.write(f" - Tâches validées : {tasks_count}")

        # 3. CROISSANCE
        new_users = CustomUser.objects.filter(date_joined__gte=yesterday).count()
        new_vips = Transaction.objects.filter(
            transaction_type='VIP_PURCHASE', status='COMPLETED', created_at__gte=yesterday
        ).values('user').distinct().count()

        self.stdout.write(self.style.SUCCESS(f"\n[CROISSANCE]"))
        self.stdout.write(f" - Nouveaux inscrits : {new_users}")
        self.stdout.write(f" - Nouveaux passages en VIP : {new_vips}")

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n--- FIN DU RAPPORT ---"))
