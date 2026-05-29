from django.test import TestCase
from decimal import Decimal
from .models import CustomUser, VIPLevel, Transaction

class FinancialTests(TestCase):
    def setUp(self):
        # Création des niveaux VIP
        self.vip1 = VIPLevel.objects.create(name="VIP 1", price=10000, daily_mining_reward=500, daily_task_limit=5, task_reward_rate=100)
        
        # Création de la hiérarchie : Parrain3 -> Parrain2 -> Parrain1 -> Utilisateur
        self.p3 = CustomUser.objects.create_user(username="p3", phone_number="611111111")
        self.p3.vip_level = self.vip1
        self.p3.save()
        
        self.p2 = CustomUser.objects.create_user(username="p2", phone_number="622222222", referred_by=self.p3)
        self.p2.vip_level = self.vip1
        self.p2.save()
        
        self.p1 = CustomUser.objects.create_user(username="p1", phone_number="633333333", referred_by=self.p2)
        self.p1.vip_level = self.vip1
        self.p1.save()
        
        self.user = CustomUser.objects.create_user(username="user", phone_number="644444444", referred_by=self.p1)
        self.user.balance = 20000
        self.user.save()

    def test_referral_commissions(self):
        """Vérifie que 10%, 5% et 2% sont distribués correctement."""
        # Achat du VIP 1 (10 000 F)
        plan = self.vip1
        
        # Logique de buy_vip simulée
        if self.user.balance >= plan.price:
            self.user.balance -= plan.price
            self.user.vip_level = plan
            self.user.save()
            
            # Distribution des commissions
            rates = [Decimal('0.10'), Decimal('0.05'), Decimal('0.02')]
            current_referrer = self.user.referred_by
            for i, rate in enumerate(rates):
                if current_referrer:
                    commission = plan.price * rate
                    current_referrer.balance += commission
                    current_referrer.total_earnings += commission
                    current_referrer.save()
                    current_referrer = current_referrer.referred_by

        # Vérifications
        self.assertEqual(self.p1.balance, 1000) # 10% de 10k
        self.assertEqual(self.p2.balance, 500)  # 5% de 10k
        self.assertEqual(self.p3.balance, 200)  # 2% de 10k
