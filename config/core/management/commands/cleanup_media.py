from django.core.management.base import BaseCommand
from core.models import UserTaskCompletion, Transaction
from django.utils import timezone
import os

class Command(BaseCommand):
    help = 'Supprime les fichiers de preuves vieux de plus de 15 jours pour libérer de l\'espace serveur'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=15, help='Nombre de jours de rétention (défaut: 15)')

    def handle(self, *args, **options):
        days = options['days']
        limit = timezone.now() - timezone.timedelta(days=days)
        
        self.stdout.write(f"Démarrage du nettoyage (seuil: {days} jours)...")

        # 1. Nettoyage des tâches (Seulement celles validées ou rejetées)
        tasks = UserTaskCompletion.objects.filter(
            completed_at__lt=limit, 
            status__in=['APPROVED', 'REJECTED']
        ).exclude(screenshot='')
        
        count_tasks = 0
        for t in tasks:
            if t.screenshot:
                try:
                    if os.path.isfile(t.screenshot.path):
                        os.remove(t.screenshot.path)
                    t.screenshot = None # On vide le champ dans la base
                    t.save()
                    count_tasks += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Erreur tâche {t.id}: {e}"))
        
        # 2. Nettoyage des dépôts (Validés ou rejetés uniquement)
        deposits = Transaction.objects.filter(
            created_at__lt=limit, 
            transaction_type='DEPOSIT',
            status__in=['COMPLETED', 'REJECTED']
        ).exclude(proof_image='')
        
        count_deposits = 0
        for d in deposits:
            if d.proof_image:
                try:
                    if os.path.isfile(d.proof_image.path):
                        os.remove(d.proof_image.path)
                    d.proof_image = None
                    d.save()
                    count_deposits += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Erreur dépôt {d.id}: {e}"))
                    
        self.stdout.write(self.style.SUCCESS(
            f'TERMINÉ : {count_tasks} captures de tâches et {count_deposits} preuves de dépôts supprimées.'
        ))
