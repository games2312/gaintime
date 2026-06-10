from django.core.management.base import BaseCommand
from core.models import DailyMission


class Command(BaseCommand):
    help = 'Crée les missions quotidiennes par défaut'

    def handle(self, *args, **options):
        missions = [
            {'mission_type': 'COMPLETE_TASKS', 'target': 3, 'reward': 30, 'description': 'Complète 3 tâches'},
            {'mission_type': 'MINE', 'target': 2, 'reward': 20, 'description': 'Lance le minage 2 fois'},
            {'mission_type': 'SPIN_WHEEL', 'target': 1, 'reward': 10, 'description': 'Tourne la roue 1 fois'},
            {'mission_type': 'CHECK_IN', 'target': 1, 'reward': 10, 'description': 'Fais ton check-in quotidien'},
            {'mission_type': 'VISIT', 'target': 1, 'reward': 5, 'description': 'Visite la plateforme'},
        ]
        created = 0
        for data in missions:
            _, is_new = DailyMission.objects.update_or_create(
                mission_type=data['mission_type'],
                defaults={
                    'target': data['target'],
                    'reward': data['reward'],
                    'description': data['description'],
                    'is_active': True,
                },
            )
            if is_new:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'{created} missions créées / mises à jour'))
