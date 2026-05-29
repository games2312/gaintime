from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, MiningSession, Task, UserTaskCompletion, Transaction, Notification, FAQ, VIPLevel, DepositMethod

@admin.register(DepositMethod)
class DepositMethodAdmin(admin.ModelAdmin):
    list_display = ('operator', 'name', 'number', 'is_active')
    list_filter = ('operator', 'is_active')
    search_fields = ('name', 'number')

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('question', 'answer')
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    
    # Colonnes affichées dans la liste
    list_display = ('username', 'phone_number', 'balance', 'invitation_code', 'referred_by', 'is_staff')
    
    # Filtres latéraux
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    
    # Champs de recherche
    search_fields = ('username', 'phone_number', 'invitation_code')
    
    # Organisation du formulaire d'édition
    fieldsets = UserAdmin.fieldsets + (
        ('Informations Supplémentaires', {
            'fields': ('phone_number', 'invitation_code', 'referred_by', 'balance'),
        }),
    )
    
    # Champs en lecture seule pour éviter la triche accidentelle par un admin junior
    readonly_fields = ('invitation_code',)

# --- Gestion des Transactions ---
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'reference_id')
    actions = ['approve_transactions', 'reject_transactions']

    @admin.action(description="Approuver les transactions sélectionnées")
    def approve_transactions(self, request, queryset):
        for transaction in queryset.filter(status='PENDING'):
            if transaction.transaction_type == 'DEPOSIT':
                transaction.user.balance += transaction.amount
                transaction.user.save()
            transaction.status = 'COMPLETED'
            transaction.save()
        self.message_user(request, "Transactions approuvées et soldes mis à jour.")

    @admin.action(description="Rejeter les transactions sélectionnées")
    def reject_transactions(self, request, queryset):
        for transaction in queryset.filter(status='PENDING'):
            if transaction.transaction_type == 'WITHDRAWAL':
                transaction.user.balance += transaction.amount
                transaction.user.save()
            transaction.status = 'REJECTED'
            transaction.save()
        self.message_user(request, "Transactions rejetées et soldes restitués (pour les retraits).")

# --- Gestion du Minage ---
@admin.register(MiningSession)
class MiningSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_time', 'end_time', 'is_active', 'is_claimed', 'earned_amount')
    list_filter = ('is_active', 'is_claimed')
    search_fields = ('user__username',)

# --- Gestion des Tâches ---
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'reward_amount', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title',)

@admin.register(UserTaskCompletion)
class UserTaskCompletionAdmin(admin.ModelAdmin):
    list_display = ('user', 'task', 'completed_at')
    list_filter = ('completed_at',)
    search_fields = ('user__username', 'task__title')