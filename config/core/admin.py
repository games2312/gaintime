from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Badge, Boost, CustomUser, DailyMission, DepositMethod, FAQ,
    MiningSession, Notification, PushSubscription, SupportTicket,
    Task, Transaction, UserBadge, UserMissionProgress, UserTaskCompletion,
    VIPLevel,
)


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
    list_display = ('username', 'phone_number', 'balance', 'invitation_code', 'referred_by', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'phone_number', 'invitation_code')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations Supplémentaires', {
            'fields': ('phone_number', 'invitation_code', 'referred_by', 'balance'),
        }),
    )
    readonly_fields = ('invitation_code',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'reference_id')
    actions = ['approve_transactions', 'reject_transactions']

    @admin.action(description="Approuver les transactions sélectionnées")
    def approve_transactions(self, request, queryset):
        for tx in queryset.filter(status='PENDING'):
            if tx.transaction_type == 'DEPOSIT':
                tx.user.balance += tx.amount
                tx.user.save()
            tx.status = 'COMPLETED'
            tx.save()
        self.message_user(request, "Transactions approuvées et soldes mis à jour.")

    @admin.action(description="Rejeter les transactions sélectionnées")
    def reject_transactions(self, request, queryset):
        for tx in queryset.filter(status='PENDING'):
            if tx.transaction_type == 'WITHDRAWAL':
                tx.user.balance += tx.amount
                tx.user.save()
            tx.status = 'REJECTED'
            tx.save()
        self.message_user(request, "Transactions rejetées et soldes restitués.")


@admin.register(MiningSession)
class MiningSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_time', 'end_time', 'is_active', 'is_claimed', 'earned_amount')
    list_filter = ('is_active', 'is_claimed')
    search_fields = ('user__username',)


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


# === NOUVEAUX MODÈLES ===

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'condition_type', 'condition_value', 'reward_amount', 'is_active')
    list_filter = ('condition_type', 'is_active')
    search_fields = ('name',)


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')
    search_fields = ('user__username', 'badge__name')


@admin.register(DailyMission)
class DailyMissionAdmin(admin.ModelAdmin):
    list_display = ('mission_type', 'target', 'reward', 'is_active')
    list_filter = ('mission_type', 'is_active')
    search_fields = ('description',)


@admin.register(UserMissionProgress)
class UserMissionProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'mission', 'progress', 'completed', 'date')
    list_filter = ('completed', 'date')
    search_fields = ('user__username',)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscribed_at')
    search_fields = ('user__username',)


@admin.register(Boost)
class BoostAdmin(admin.ModelAdmin):
    list_display = ('name', 'boost_type', 'price', 'quantity', 'duration_hours', 'is_active')
    list_filter = ('boost_type', 'is_active')
    search_fields = ('name',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'title')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'subject')
