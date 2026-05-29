from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from decimal import Decimal
import random
import string

# --- VALIDATEURS ---
phone_validator = RegexValidator(
    regex=r'^(6|2)[0-9]{8}$',
    message="Le numéro doit être un format camerounais valide (9 chiffres, ex: 6xxxxxxxx)."
)

def generate_invitation_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- MODÈLES ---

CATEGORY_CHOICES = [
    ('trading', 'Trading'),
    ('dropshipping', 'Dropshipping'),
    ('content_creation', 'Création de contenu'),
    ('digital_products', 'Vente de produits digitaux'),
    ('freelancing', 'Freelancing'),
    ('sports_betting', 'Paris Sportifs'),
    ('development', 'Développement & Informatique'),
    ('graphic_design', 'Design & Multimédia'),
    ('digital_marketing', 'Marketing Digital'),
    ('general', 'Général'),
    ('other', 'Autre'),
]

class VIPLevel(models.Model):
    """
    Configuration des niveaux VIP (Prix, Gains, Limites).
    """
    name = models.CharField(max_length=50, verbose_name="Nom du Niveau") # Ex: VIP 1, Bronze
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix d'achat")
    
    # Avantages
    daily_mining_reward = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Gain Minage (par session)")
    daily_task_limit = models.IntegerField(default=0, verbose_name="Nb Tâches / Jour")
    task_reward_rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Gain par Tâche")
    
    # Nouveau : Récompense de parrainage quand un filleul commence à miner
    referral_reward = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('500.00'), verbose_name="Bonus Parrainage (Invitation)")
    
    # Durée de validité (en jours)
    validity_days = models.IntegerField(default=120, verbose_name="Validité (Jours)")
    
    image = models.CharField(max_length=100, blank=True, null=True, verbose_name="Icône (ex: fas fa-crown)")

    def __str__(self):
        return f"{self.name} - {self.price} FCFA"
    
    class Meta:
        verbose_name = "Niveau VIP"
        verbose_name_plural = "Niveaux VIP"
        ordering = ['price']

class Notification(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.IntegerField(default=0, verbose_name="Ordre d'affichage")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ['order']

    def __str__(self):
        return self.question

class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=15, unique=True, validators=[phone_validator], verbose_name="Numéro de portable")
    invitation_code = models.CharField(max_length=10, unique=True, verbose_name="Code d'invitation")
    referred_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Gestion VIP
    vip_level = models.ForeignKey(VIPLevel, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Niveau VIP Actuel")
    vip_expiry_date = models.DateTimeField(null=True, blank=True, verbose_name="Expiration VIP")

    # Anti-fraude parrainage
    has_triggered_referral_bonus = models.BooleanField(default=False, verbose_name="A déjà généré un bonus parrain")
    device_fingerprint = models.CharField(max_length=128, blank=True, null=True, db_index=True, verbose_name="Empreinte appareil")

    # Bonus Quotidien
    last_check_in = models.DateField(null=True, blank=True, verbose_name="Dernier Check-in")
    check_in_streak = models.IntegerField(default=0, verbose_name="Série actuelle")
    last_spin_time = models.DateTimeField(null=True, blank=True, verbose_name="Dernier tour de roue")
    free_spins = models.IntegerField(default=0, verbose_name="Tours gratuits bonus")

    # Sécurité Multi-comptes
    registration_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Inscription")
    last_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dernière IP connue")

    # Nouveau : Badge de confiance
    is_verified = models.BooleanField(default=False, verbose_name="Compte Vérifié")
    is_phone_verified = models.BooleanField(default=False, verbose_name="Téléphone Vérifié")
    otp_code = models.CharField(max_length=6, blank=True, null=True, verbose_name="Code OTP")
    has_seen_onboarding = models.BooleanField(default=False, verbose_name="A vu le tutoriel")

    # Personnalisation Communauté
    has_completed_survey = models.BooleanField(default=False, verbose_name="Sondage complété")
    interests = models.CharField(max_length=255, blank=True, null=True, verbose_name="Centres d'intérêt")
    survey_data = models.JSONField(default=dict, blank=True, null=True, verbose_name="Données détaillées du sondage")

    # Paliers de parrainage
    referral_tier = models.IntegerField(default=0, verbose_name="Palier parrainage")
    total_referrals = models.IntegerField(default=0, verbose_name="Total filleuls directs")

    # Gamification
    trust_score = models.IntegerField(default=0, verbose_name="Score de confiance")
    badges = models.ManyToManyField('Badge', through='UserBadge', blank=True)

    # Boosts actifs
    turbo_mining_until = models.DateTimeField(null=True, blank=True, verbose_name="Turbo minage jusqu'à")
    extra_tasks_today = models.IntegerField(default=0, verbose_name="Tâches supplémentaires aujourd'hui")

    # Statistiques et Sécurité Financière
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Gains Totaux cumulés")
    withdrawal_phone_locked = models.CharField(max_length=15, blank=True, null=True, verbose_name="Numéro de retrait verrouillé")

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invitation_code:
            code = generate_invitation_code()
            while CustomUser.objects.filter(invitation_code=code).exists():
                code = generate_invitation_code()
            self.invitation_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.vip_level.name if self.vip_level else 'Gratuit'})"

    class Meta:
        indexes = [
            models.Index(fields=['registration_ip', 'last_ip']),
            models.Index(fields=['referred_by']),
            models.Index(fields=['device_fingerprint']),
        ]

class MiningSession(models.Model):
    DURATION_HOURS = 12
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_claimed = models.BooleanField(default=False)
    earned_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def save(self, *args, **kwargs):
        if not self.end_time:
            self.end_time = timezone.now() + timezone.timedelta(hours=self.DURATION_HOURS)
        super().save(*args, **kwargs)
    
    @property
    def is_completed(self):
        return timezone.now() >= self.end_time

class DepositMethod(models.Model):
    OPERATOR_CHOICES = (
        ('OM', 'Orange Money'),
        ('MOMO', 'MTN MoMo'),
    )
    operator = models.CharField(max_length=10, choices=OPERATOR_CHOICES)
    name = models.CharField(max_length=100, verbose_name="Nom du bénéficiaire")
    number = models.CharField(max_length=20, verbose_name="Numéro de téléphone")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Méthode de dépôt"
        verbose_name_plural = "Méthodes de dépôt"

    def __str__(self):
        return f"{self.get_operator_display()} - {self.name} ({self.number})"

class Task(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    platform = models.CharField(max_length=50, choices=[
        ('youtube', 'YouTube'), 
        ('facebook', 'Facebook'), 
        ('tiktok', 'TikTok'), 
        ('whatsapp', 'WhatsApp'), 
        ('instagram', 'Instagram'), 
        ('telegram', 'Telegram'), 
        ('internal', 'Plateforme'),
        ('other', 'Autre')
    ], default='other')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general', verbose_name="Catégorie")
    link = models.URLField(blank=True, null=True)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Nouveau : Compte à rebours
    duration_seconds = models.PositiveIntegerField(default=30, verbose_name="Durée (secondes)")
    is_automatic = models.BooleanField(default=False, verbose_name="Validation automatique (Timer)")
    
    # Restriction VIP
    min_vip_required = models.ForeignKey(VIPLevel, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="VIP Min Requis")
    
    # Nouveau : Preuve par lien
    requires_link_proof = models.BooleanField(default=False, verbose_name="Nécessite un lien de preuve")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class UserTaskCompletion(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('APPROVED', 'Validé'),
        ('REJECTED', 'Rejeté'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    # Remplacement de ImageField par FileField pour éviter l'erreur Pillow si l'installation échoue
    screenshot = models.FileField(upload_to='tasks/proofs/', null=True, blank=True, verbose_name="Capture d'écran")
    proof_link = models.URLField(max_length=500, null=True, blank=True, verbose_name="Lien de preuve")
    image_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name="Hash de l'image")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    completed_at = models.DateTimeField(auto_now_add=True) # Date précise pour vérifier la limite journalière

    class Meta:
        verbose_name = "Tâche réalisée"
        verbose_name_plural = "Tâches réalisées"

class SupportTicket(models.Model):
    STATUS_CHOICES = (
        ('OPEN', 'Ouvert'),
        ('PENDING', 'En cours'),
        ('CLOSED', 'Fermé'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tickets')
    subject = models.CharField(max_length=200, verbose_name="Sujet")
    message = models.TextField(verbose_name="Message")
    admin_reply = models.TextField(blank=True, null=True, verbose_name="Réponse Admin")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ticket de Support"
        verbose_name_plural = "Tickets de Support"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.subject} - {self.user.username}"

class Transaction(models.Model):
    TYPE_CHOICES = (
        ('DEPOSIT', 'Dépôt'),
        ('WITHDRAWAL', 'Retrait'),
        ('MINING_REWARD', 'Gain Minage'),
        ('TASK_REWARD', 'Gain Tâche'),
        ('VIP_PURCHASE', 'Achat VIP'),
        ('REFERRAL_BONUS', 'Bonus Parrainage'),
        ('DAILY_CHECKIN', 'Bonus Quotidien'),
        ('SPIN_WIN', 'Roue de la Fortune'),
        ('BOOST_PURCHASE', 'Achat Boost'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('COMPLETED', 'Validé'),
        ('REJECTED', 'Rejeté'),
    )
    METHOD_CHOICES = (('OM', 'Orange Money'), ('MOMO', 'MTN MoMo'), ('SYSTEM', 'Système'))

    user = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='transactions')
    from_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_transactions', verbose_name="Généré par")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='SYSTEM')
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    proof_image = models.FileField(upload_to='deposits/proofs/', null=True, blank=True, verbose_name="Preuve de dépôt")
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'transaction_type', 'status', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount}"


class Boost(models.Model):
    BOOST_TYPES = (
        ('TURBO_MINING', 'Turbo Mining'),
        ('FREE_SPIN_PACK', 'Pack Tours Gratuits'),
        ('EXTRA_TASKS', 'Tâches Supplémentaires'),
        ('DOUBLE_REWARD', 'Gain Doublé'),
        ('WITHDRAWAL_PRIORITY', 'Retrait Prioritaire'),
    )
    name = models.CharField(max_length=50)
    boost_type = models.CharField(max_length=30, choices=BOOST_TYPES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    quantity = models.IntegerField(default=1, help_text="Quantité délivrée (ex: 5 tours)")
    duration_hours = models.IntegerField(default=0, help_text="Durée en heures (0 = immédiat)")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} - {self.price} F"


class Badge(models.Model):
    CONDITION_CHOICES = (
        ('TASKS_COMPLETED', 'Tâches complétées'),
        ('REFERRALS', 'Filleuls parrainés'),
        ('TOTAL_EARNED', 'Gains totaux'),
        ('CHECKIN_STREAK', 'Série check-in'),
        ('VIP_PURCHASE', 'Achat VIP'),
        ('DAYS_ACTIVE', 'Jours actifs'),
    )
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='fa-star', help_text="Classe FontAwesome")
    condition_type = models.CharField(max_length=30, choices=CONDITION_CHOICES)
    condition_value = models.IntegerField(help_text="Valeur à atteindre")
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['condition_value']

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='earned_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self):
        return f"{self.user.username} → {self.badge.name}"


class DailyMission(models.Model):
    MISSION_TYPES = (
        ('COMPLETE_TASKS', 'Compléter des tâches'),
        ('MINE', 'Lancer le minage'),
        ('SPIN_WHEEL', 'Tourner la roue'),
        ('CHECK_IN', 'Check-in quotidien'),
        ('VISIT', 'Visiter la plateforme'),
    )
    mission_type = models.CharField(max_length=30, choices=MISSION_TYPES)
    target = models.IntegerField(default=1, help_text="Objectif à atteindre")
    reward = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['mission_type']

    def __str__(self):
        return f"{self.get_mission_type_display()} - {self.reward} F"


class UserMissionProgress(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='missions')
    mission = models.ForeignKey(DailyMission, on_delete=models.CASCADE)
    progress = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'mission', 'date')

    def __str__(self):
        return f"{self.user.username} - {self.mission.mission_type}: {self.progress}/{self.mission.target}"


class PushSubscription(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=500)
    auth_key = models.CharField(max_length=100, blank=True)
    p256dh_key = models.CharField(max_length=100, blank=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'endpoint')