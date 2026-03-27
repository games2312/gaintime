from django.core.management.base import BaseCommand
from core.models import UserTaskCompletion, Transaction
from django.utils import timezone
import os

class Command(BaseCommand):
    help = 'Supprime les fichiers de preuves vieux de plus de 30 jours'

    def handle(self, *args, **options):
        limit = timezone.now() - timezone.timedelta(days=30)
        
        # Nettoyage des tâches
        tasks = UserTaskCompletion.objects.filter(completed_at__lt=limit)
        for t in tasks:
            if t.screenshot:
                if os.path.isfile(t.screenshot.path):
                    os.remove(t.screenshot.path)
        
        # Nettoyage des dépôts
        deposits = Transaction.objects.filter(created_at__lt=limit, transaction_type='DEPOSIT')
        for d in deposits:
            if d.proof_image:
                if os.path.isfile(d.proof_image.path):
                    os.remove(d.proof_image.path)
                    
        self.stdout.write(self.style.SUCCESS('Nettoyage des anciens fichiers terminé.'))
