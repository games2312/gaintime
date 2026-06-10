import csv
import json
import logging
import random

from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.views import LoginView
from django.db import models, transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .forms import RegisterForm, LoginForm, TaskForm, VIPLevelForm
from .models import (
    Announcement, Badge, Boost, CustomUser, DailyMission, DepositMethod, FAQ,
    MiningSession, Notification, SupportTicket, Task, Transaction,
    UserBadge, UserMissionProgress, UserTaskCompletion, VIPLevel,
)
from .utils import award_xp, check_referral_tiers, compute_phash, get_client_ip, hamming_distance, update_mission_progress, validate_image_magic_bytes, LEVEL_THRESHOLDS

logger = logging.getLogger(__name__)

@staff_member_required(login_url='/management/login/')
def admin_manage_vip(request):
    vips = VIPLevel.objects.all().order_by('price')
    return render(request, 'core/admin/manage_vip.html', {'vips': vips})

@staff_member_required(login_url='/management/login/')
def admin_add_vip(request):
    if request.method == 'POST':
        form = VIPLevelForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pack VIP créé.")
            return redirect('admin_manage_vip')
    else:
        form = VIPLevelForm()
    return render(request, 'core/admin/edit_vip.html', {'form': form, 'action': 'Ajouter'})

@staff_member_required(login_url='/management/login/')
def admin_edit_vip(request, vip_id):
    vip = get_object_or_404(VIPLevel, id=vip_id)
    if request.method == 'POST':
        form = VIPLevelForm(request.POST, instance=vip)
        if form.is_valid():
            form.save()
            messages.success(request, "Pack VIP mis à jour.")
            return redirect('admin_manage_vip')
    else:
        form = VIPLevelForm(instance=vip)
    return render(request, 'core/admin/edit_vip.html', {'form': form, 'action': 'Modifier'})

@staff_member_required(login_url='/management/login/')
def admin_delete_vip(request, vip_id):
    vip = get_object_or_404(VIPLevel, id=vip_id)
    if vip.price == 0:
        messages.error(request, "Le pack Gratuit ne peut pas être supprimé.")
    else:
        vip.delete()
        messages.warning(request, "Pack VIP supprimé.")
    return redirect('admin_manage_vip')

@staff_member_required(login_url='/management/login/')
def admin_manage_tasks(request):
    tasks = Task.objects.all().order_by('-id')
    return render(request, 'core/admin/manage_tasks.html', {'tasks': tasks})

@staff_member_required(login_url='/management/login/')
def admin_add_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.reward_amount = Decimal('0.00') # Fixé à 0 car géré par le VIP
            task.save()
            messages.success(request, "Tâche créée avec succès.")
            return redirect('admin_manage_tasks')
    else:
        form = TaskForm()
    return render(request, 'core/admin/edit_task.html', {'form': form, 'action': 'Ajouter'})

@staff_member_required(login_url='/management/login/')
def admin_edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Tâche mise à jour.")
            return redirect('admin_manage_tasks')
    else:
        form = TaskForm(instance=task)
    return render(request, 'core/admin/edit_task.html', {'form': form, 'action': 'Modifier'})

@staff_member_required(login_url='/management/login/')
def admin_delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    messages.warning(request, "Tâche supprimée.")
    return redirect('admin_manage_tasks')


# --- PAGES PUBLIQUES ---

def home(request):
    return render(request, 'core/accueil_gaintime.html')

@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            client_ip = get_client_ip(request)
            
            # SECURITÉ : On limite à 2 comptes par adresse IP
            accounts_count = CustomUser.objects.filter(registration_ip=client_ip).count()
            if accounts_count >= 2:
                messages.error(request, "Désolé, vous avez atteint la limite de comptes autorisés pour cette connexion.")
                return render(request, 'core/inscription_reward.html', {'form': form})
                
            user = form.save(commit=False)
            user.registration_ip = client_ip
            user.last_ip = client_ip
            user.device_fingerprint = request.POST.get('device_fingerprint', '')[:128]
            user.is_phone_verified = True
            user.save()
            
            free_level = VIPLevel.objects.filter(price=0).first()
            if free_level:
                user.vip_level = free_level
                user.save()

            if user.referred_by:
                referrer = user.referred_by
                check_referral_tiers(referrer)
            
            award_xp(user, 20, "Inscription")
            messages.success(request, "Inscription réussie !")
            login(request, user)
            return redirect('dashboard')
    else:
        form = RegisterForm(initial={'invitation_code_input': request.GET.get('ref', '')})
    return render(request, 'core/inscription_reward.html', {'form': form})

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            user.last_ip = get_client_ip(request)
            fingerprint = request.POST.get('device_fingerprint', '')
            if fingerprint and not user.device_fingerprint:
                user.device_fingerprint = fingerprint[:128]
            user.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = LoginForm()
    return render(request, 'core/conneexion_reward.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('home')

# --- DASHBOARD & NAVIGATION ---

@login_required
def dashboard(request):
    today = timezone.now().date()
    if request.session.get('visited_today') != str(today):
        request.session['visited_today'] = str(today)
        update_mission_progress(request.user, 'VISIT')
    
    active_session = MiningSession.objects.filter(user=request.user, is_active=True).first()
    
    # On calcule la somme de TOUS les gains de la journée
    reward_types = ['MINING_REWARD', 'TASK_REWARD', 'REFERRAL_BONUS', 'DAILY_CHECKIN', 'SPIN_WIN']
    daily_earnings = Transaction.objects.filter(
        user=request.user, 
        transaction_type__in=reward_types,
        status='COMPLETED',
        created_at__date=today
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Calcul du temps restant en secondes
    remaining_seconds = 0
    mining_completed = False
    if active_session:
        now = timezone.now()
        delta = active_session.end_time - now
        remaining_seconds = int(delta.total_seconds())
        
        if remaining_seconds <= 0:
            remaining_seconds = 0
            mining_completed = True
            active_session = None
        else:
            mining_completed = False

    # Données pour le graphique des gains (7 derniers jours)
    seven_days_ago = today - timezone.timedelta(days=6)
    daily_stats = Transaction.objects.filter(
        user=request.user,
        transaction_type__in=reward_types,
        status='COMPLETED',
        created_at__date__gte=seven_days_ago
    ).annotate(day=TruncDate('created_at')).values('day').annotate(total=models.Sum('amount')).order_by('day')
    
    # Préparation des labels et données pour Chart.js
    graph_labels = []
    graph_data = []
    stats_dict = {str(s['day']): float(s['total']) for s in daily_stats}
    
    for i in range(7):
        day = seven_days_ago + timezone.timedelta(days=i)
        day_str = str(day)
        graph_labels.append(day.strftime('%d/%m'))
        graph_data.append(stats_dict.get(day_str, 0))

    weekly_total = sum(graph_data)

    user_level = request.user.level
    next_xp = None
    for lvl, needed in sorted(LEVEL_THRESHOLDS.items()):
        if lvl > user_level:
            next_xp = needed
            break

    context = {
        'active_session': active_session,
        'remaining_seconds': remaining_seconds,
        'daily_earnings': daily_earnings,
        'completed_tasks': UserTaskCompletion.objects.filter(user=request.user, completed_at__date=today).count(),
        'total_tasks': request.user.vip_level.daily_task_limit if request.user.vip_level else 2,
        'mining_completed': mining_completed,
        'today_date': today,
        'weekly_total': weekly_total,
        'graph_labels': graph_labels,
        'graph_data': graph_data,
        'next_level_xp': next_xp,
    }
    return render(request, 'core/dashboard_reward.html', context)

@login_required
def survey_view(request):
    if request.user.has_completed_survey:
        return redirect('tasks')
    return render(request, 'core/survey.html')

@login_required
def submit_survey(request):
    if request.method == 'POST':
        interests_list = request.POST.getlist('interests')
        if not interests_list:
            messages.error(request, "Veuillez choisir au moins un centre d'intérêt pour continuer.")
            return redirect('survey')
        
        # Collecte de toutes les réponses spécifiques
        survey_results = {
            'trading': {
                'level': request.POST.get('trading_level'),
                'market': request.POST.get('trading_market')
            } if 'trading' in interests_list else None,
            'dropshipping': {
                'status': request.POST.get('dropshipping_status'),
                'need': request.POST.get('dropshipping_need')
            } if 'dropshipping' in interests_list else None,
            'freelancing': {
                'skill': request.POST.get('freelancing_skill')
            } if 'freelancing' in interests_list else None,
            'sports_betting': {
                'profile': request.POST.get('betting_profile'),
                'want_pronos': request.POST.get('want_pronos') == 'yes'
            } if 'sports_betting' in interests_list else None,
            'development': {
                'domain': request.POST.get('dev_domain')
            } if 'development' in interests_list else None,
            'graphic_design': {
                'tool': request.POST.get('design_tool')
            } if 'graphic_design' in interests_list else None,
            'digital_marketing': {
                'goal': request.POST.get('marketing_goal')
            } if 'digital_marketing' in interests_list else None
        }

        # Nettoyage pour ne garder que les données pertinentes
        cleaned_data = {k: v for k, v in survey_results.items() if v is not None}

        request.user.interests = ",".join(interests_list)
        request.user.survey_data = cleaned_data # On stocke tout au format JSON
        request.user.has_completed_survey = True
        request.user.save()

        messages.success(request, "Merci ! Vos opportunités sont désormais personnalisées à 100%.")
        return redirect('tasks')
    return redirect('survey')

@login_required
def tasks_view(request):
    if not request.user.has_completed_survey:
        return redirect('survey')

    user_level = request.user.vip_level or VIPLevel.objects.filter(price=0).first()
    
    # Filtrage des tâches par intérêts de l'utilisateur + tâches générales
    user_interests = request.user.interests.split(',') if request.user.interests else []
    tasks_query = Task.objects.filter(is_active=True).filter(
        models.Q(category='general') | models.Q(category__in=user_interests)
    )
    
    all_tasks = list(tasks_query)
    
    random.shuffle(all_tasks)
    
    today = timezone.now().date()
    completed_task_ids = UserTaskCompletion.objects.filter(user=request.user, completed_at__date=today).values_list('task_id', flat=True)
    
    return render(request, 'core/taches_reward.html', {
        'tasks': all_tasks,
        'completed_task_ids': completed_task_ids,
        'user_level': user_level,
        'tasks_done_count': len(completed_task_ids),
        'daily_limit': user_level.daily_task_limit + request.user.extra_tasks_today
    })

@login_required
def mining_view(request):
    active_session = MiningSession.objects.filter(user=request.user, is_active=True).first()
    history = MiningSession.objects.filter(user=request.user).order_by('-start_time')[:10]
    
    remaining_seconds = 0
    mining_completed = False
    
    if active_session:
        now = timezone.now()
        delta = active_session.end_time - now
        remaining_seconds = int(delta.total_seconds())
        
        # Si le temps est écoulé, on considère la session comme terminée pour l'affichage
        if remaining_seconds <= 0:
            remaining_seconds = 0
            mining_completed = True
            active_session = None 
        else:
            mining_completed = False
            
    return render(request, 'core/minage_reward.html', {
        'active_session': active_session,
        'remaining_seconds': remaining_seconds,
        'history': history,
        'mining_completed': mining_completed,
    })

@login_required
def team_view(request):
    user = request.user

    def get_referrals_with_earnings(referrals_query):
        return referrals_query.annotate(
            earned_for_me=Sum(
                'generated_transactions__amount',
                filter=models.Q(generated_transactions__user=user, generated_transactions__transaction_type='REFERRAL_BONUS')
            )
        )

    # Niveau 1
    referrals_l1 = get_referrals_with_earnings(user.referrals.all())
    
    # Niveau 2
    referrals_l2 = get_referrals_with_earnings(CustomUser.objects.filter(referred_by__in=user.referrals.all()))
    
    # Niveau 3
    referrals_l3 = get_referrals_with_earnings(CustomUser.objects.filter(referred_by__in=CustomUser.objects.filter(referred_by__in=user.referrals.all())))
    
    # Commissions totales
    total_commissions = Transaction.objects.filter(
        user=user, 
        transaction_type='REFERRAL_BONUS',
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'referrals_l1': referrals_l1,
        'referrals_l2': referrals_l2,
        'referrals_l3': referrals_l3,
        'total_referrals': referrals_l1.count() + referrals_l2.count() + referrals_l3.count(),
        'total_commissions': total_commissions
    }
    return render(request, 'core/equipe_reward.html', context)

@login_required
def leaderboard_view(request):
    # Top 10 des utilisateurs par gains totaux
    top_users = CustomUser.objects.filter(is_active=True).order_by('-total_earnings')[:10]
    
    # Position de l'utilisateur actuel
    user_rank = CustomUser.objects.filter(total_earnings__gt=request.user.total_earnings).count() + 1
    
    return render(request, 'core/classement.html', {
        'top_users': top_users,
        'user_rank': user_rank
    })

@login_required
def profile_view(request):
    return render(request, 'core/profil_reward.html')

@login_required
def wallet_view(request):
    tx_filter = Transaction.objects.filter(user=request.user)
    tx_type = request.GET.get('type', '')
    tx_status = request.GET.get('status', '')
    tx_q = request.GET.get('q', '').strip()
    type_choices = dict(Transaction.TYPE_CHOICES)
    if tx_type in type_choices:
        tx_filter = tx_filter.filter(transaction_type=tx_type)
    if tx_status in ['PENDING', 'COMPLETED', 'REJECTED']:
        tx_filter = tx_filter.filter(status=tx_status)
    if tx_q:
        tx_filter = tx_filter.filter(
            models.Q(description__icontains=tx_q) |
            models.Q(reference_id__icontains=tx_q) |
            models.Q(amount__icontains=tx_q)
        )
    paginator = Paginator(tx_filter.order_by('-created_at'), 20)
    page = request.GET.get('page', 1)
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
    return render(request, 'core/portefeuille.html', {
        'transactions': transactions,
        'filter_type': tx_type,
        'filter_status': tx_status,
        'search_q': tx_q,
        'tx_type_choices': Transaction.TYPE_CHOICES,
    })

@login_required
def communaute_view(request):
    if not request.user.has_completed_survey:
        messages.warning(request, "Veuillez d'abord personnaliser votre profil pour accéder à la communauté.")
        return redirect('survey')
    
    # On récupère les intérêts sous forme de liste pour le template
    user_interests = request.user.interests.split(',') if request.user.interests else []
    
    context = {
        'interests': user_interests,
        'data': request.user.survey_data,
        'username': request.user.username
    }
    return render(request, 'core/communaute.html', context)

@login_required
def notifications_view(request):
    notifications = request.user.notifications.all()
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'core/notifications.html', {'notifications': notifications})

def faq_view(request):
    faqs = FAQ.objects.filter(is_active=True)
    return render(request, 'core/faq.html', {'faqs': faqs})

@login_required
def wheel_view(request):
    user = request.user
    can_spin = False
    remaining_seconds = 0
    
    # Priorité aux tours bonus
    if user.free_spins > 0:
        can_spin = True
    else:
        if not user.last_spin_time:
            can_spin = True
        else:
            now = timezone.now()
            next_spin_time = user.last_spin_time + timezone.timedelta(hours=24)
            if now >= next_spin_time:
                can_spin = True
            else:
                remaining_seconds = int((next_spin_time - now).total_seconds())
                
    return render(request, 'core/roue_reward.html', {
        'can_spin': can_spin, 
        'remaining_seconds': remaining_seconds,
        'free_spins': user.free_spins
    })

@login_required
def spin_wheel(request):
    if request.method == 'POST':
        user = request.user
        now = timezone.now()
        
        use_free_spin = False
        if user.free_spins > 0:
            use_free_spin = True
        elif user.last_spin_time and now < (user.last_spin_time + timezone.timedelta(hours=24)):
            return JsonResponse({'success': False, 'message': 'Pas encore disponible !'})
            
        prizes = [
            {'amount': 5, 'weight': 40, 'label': '5 F'},
            {'amount': 10, 'weight': 30, 'label': '10 F'},
            {'amount': 20, 'weight': 15, 'label': '20 F'},
            {'amount': 0, 'weight': 10, 'label': 'PERDU'},
            {'amount': 50, 'weight': 4, 'label': '50 F'},
            {'amount': 100, 'weight': 1, 'label': '100 F'},
        ]
        
        choice = random.choices(prizes, weights=[p['weight'] for p in prizes], k=1)[0]
        amount = Decimal(str(choice['amount']))
        
        if amount > 0:
            user.balance += amount
            user.total_earnings += amount
            Transaction.objects.create(
                user=user, amount=amount, transaction_type='SPIN_WIN',
                status='COMPLETED', description="Gain Roue de la Fortune"
            )
            
        if use_free_spin:
            user.free_spins -= 1
        else:
            user.last_spin_time = now
            
        user.save()
        update_mission_progress(user, 'SPIN_WHEEL')
        
        return JsonResponse({
            'success': True, 
            'amount': float(amount),
            'label': choice['label'],
            'index': prizes.index(choice)
        })
    return JsonResponse({'success': False})

@login_required
def vip_plans_view(request):
    plans = VIPLevel.objects.all().order_by('price')
    return render(request, 'core/plan_investissement_reward.html', {'plans': plans})

@login_required
def boosts_view(request):
    boosts = Boost.objects.filter(is_active=True)
    return render(request, 'core/boosts.html', {'boosts': boosts})

@login_required
def buy_boost(request, boost_id):
    boost = get_object_or_404(Boost, id=boost_id, is_active=True)
    user = request.user
    if request.method == 'POST':
        if user.balance < boost.price:
            messages.error(request, "Solde insuffisant.")
            return redirect('boosts')
        user.balance -= boost.price
        now = timezone.now()
        if boost.boost_type == 'TURBO_MINING':
            if user.turbo_mining_until and user.turbo_mining_until > now:
                user.turbo_mining_until += timezone.timedelta(hours=boost.duration_hours)
            else:
                user.turbo_mining_until = now + timezone.timedelta(hours=boost.duration_hours)
        elif boost.boost_type == 'FREE_SPIN_PACK':
            user.free_spins += boost.quantity
        elif boost.boost_type == 'EXTRA_TASKS':
            user.extra_tasks_today += boost.quantity
        user.save()
        Transaction.objects.create(
            user=user, amount=boost.price, transaction_type='BOOST_PURCHASE',
            status='COMPLETED', description=f"Boost: {boost.name}"
        )
        messages.success(request, f"Boost {boost.name} activé !")
    return redirect('boosts')

@login_required
def referral_program_view(request):
    tiers = [
        {'level': 1, 'needed': 3, 'bonus': '+1% commission sur achats VIP des filleuls', 'reward': 500},
        {'level': 2, 'needed': 10, 'bonus': '+2% commission + accès groupe Telegram privé', 'reward': 2000},
        {'level': 3, 'needed': 25, 'bonus': '+3% commission + badge exclusif', 'reward': 5000},
        {'level': 4, 'needed': 50, 'bonus': '+4% commission + retrait prioritaire', 'reward': 15000},
        {'level': 5, 'needed': 100, 'bonus': '+5% commission + cashback VIP 50%', 'reward': 50000},
    ]
    referral_earnings = Transaction.objects.filter(
        user=request.user, transaction_type='REFERRAL_BONUS', status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    top_referrers = CustomUser.objects.filter(total_referrals__gt=0).order_by('-total_referrals')[:20]
    return render(request, 'core/referral_program.html', {
        'tiers': tiers,
        'current_tier': request.user.referral_tier,
        'total_referrals': request.user.total_referrals,
        'referral_earnings': referral_earnings,
        'top_referrers': top_referrers,
    })


@login_required
def gamification_view(request):
    user = request.user
    user.trust_score = compute_trust_score(user)
    check_badge_unlocks(user)
    user.save()

    today = timezone.now().date()
    earned_badges = UserBadge.objects.filter(user=user).select_related('badge')
    missions = DailyMission.objects.filter(is_active=True)
    mission_progress = UserMissionProgress.objects.filter(user=user, date=today).select_related('mission')

    return render(request, 'core/gamification.html', {
        'trust_score': user.trust_score,
        'earned_badges': earned_badges,
        'missions': missions,
        'mission_progress': {mp.mission_id: mp for mp in mission_progress},
    })


@login_required
def chat_view(request):
    return render(request, 'core/chat.html')


def compute_trust_score(user):
    score = 0
    now = timezone.now()
    days_active = (now - user.date_joined).days if user.date_joined else 0
    score += min(days_active * 5, 30)
    tasks_ok = UserTaskCompletion.objects.filter(user=user, status='APPROVED').count()
    score += tasks_ok * 2
    deposits = Transaction.objects.filter(user=user, transaction_type='DEPOSIT', status='COMPLETED').aggregate(
        total=Sum('amount'))['total'] or 0
    score += min(int(deposits / 1000) * 10, 40)
    referrals_count = CustomUser.objects.filter(referred_by=user).count()
    score += referrals_count * 15
    if user.is_phone_verified:
        score += 25
    if user.vip_level and user.vip_level.price > 0:
        score += 20
    if user.is_active is False:
        score = 0
    return min(score, 100)


def check_badge_unlocks(user):
    now = timezone.now()
    days_active = (now - user.date_joined).days if user.date_joined else 0
    tasks_ok = UserTaskCompletion.objects.filter(user=user, status='APPROVED').count()
    referrals_count = CustomUser.objects.filter(referred_by=user).count()

    badges = Badge.objects.filter(is_active=True)
    for badge in badges:
        if UserBadge.objects.filter(user=user, badge=badge).exists():
            continue
        unlocked = False
        if badge.condition_type == 'TASKS_COMPLETED' and tasks_ok >= badge.condition_value:
            unlocked = True
        elif badge.condition_type == 'REFERRALS' and referrals_count >= badge.condition_value:
            unlocked = True
        elif badge.condition_type == 'TOTAL_EARNED' and user.total_earnings >= badge.condition_value:
            unlocked = True
        elif badge.condition_type == 'CHECKIN_STREAK' and user.check_in_streak >= badge.condition_value:
            unlocked = True
        elif badge.condition_type == 'VIP_PURCHASE' and user.vip_level and user.vip_level.price > 0:
            unlocked = True
        elif badge.condition_type == 'DAYS_ACTIVE' and days_active >= badge.condition_value:
            unlocked = True
        if unlocked:
            UserBadge.objects.create(user=user, badge=badge)
            if badge.reward_amount > 0:
                user.balance += badge.reward_amount
                user.total_earnings += badge.reward_amount
                Transaction.objects.create(
                    user=user, amount=badge.reward_amount,
                    transaction_type='TASK_REWARD', status='COMPLETED',
                    description=f"Badge débloqué: {badge.name}"
                )
            user.save()
            try:
                from .tasks import send_push_badge_unlocked
                send_push_badge_unlocked.delay(user.id, badge.name)
            except Exception:
                pass


def offline_view(request):
    return render(request, 'core/offline.html')


@login_required
def gamification_view(request):
    user = request.user
    user.trust_score = compute_trust_score(user)
    check_badge_unlocks(user)
    user.save()

    today = timezone.now().date()
    earned_badges = UserBadge.objects.filter(user=user).select_related('badge')
    missions = DailyMission.objects.filter(is_active=True)
    mission_progress = UserMissionProgress.objects.filter(user=user, date=today).select_related('mission')

    return render(request, 'core/gamification.html', {
        'trust_score': user.trust_score,
        'earned_badges': earned_badges,
        'missions': missions,
        'mission_progress': {mp.mission_id: mp for mp in mission_progress},
    })

# --- ACTIONS ---

@login_required
def buy_vip(request, plan_id):
    plan = get_object_or_404(VIPLevel, id=plan_id)
    user = request.user
    
    # 1. Empêcher l'achat d'un pack inférieur
    if user.vip_level and user.vip_level.price > plan.price:
        messages.error(request, f"Vous possédez déjà un pack supérieur ({user.vip_level.name}).")
        return redirect('vip_plans')

    if request.method == 'POST':
        if user.balance >= plan.price:
            user.balance -= plan.price
            
            # 2. Logique de date intelligente
            now = timezone.now()
            # Si l'utilisateur a déjà ce pack exact et qu'il n'est pas expiré, on CUMULE
            if user.vip_level == plan and user.vip_expiry_date and user.vip_expiry_date > now:
                user.vip_expiry_date += timezone.timedelta(days=plan.validity_days)
                messages.success(request, f"Votre abonnement {plan.name} a été prolongé de {plan.validity_days} jours !")
            else:
                # Sinon (nouveau pack supérieur ou pack expiré), on remplace et on met 120 jours
                user.vip_level = plan
                user.vip_expiry_date = now + timezone.timedelta(days=plan.validity_days)
                messages.success(request, f"Félicitations ! Vous êtes maintenant {plan.name}")
            
            # On vérifie le compte si c'est un pack payant
            if plan.price > 0:
                user.is_verified = True
                
            user.save()
            
            # Transaction pour l'achat
            Transaction.objects.create(
                user=user,
                amount=plan.price,
                transaction_type='VIP_PURCHASE',
                status='COMPLETED',
                description=f"Achat/Prolongation niveau {plan.name}"
            )

            # --- LOGIQUE DE PARRAINAGE MULTI-NIVEAUX (3 NIVEAUX) ---
            rates = [Decimal('0.10'), Decimal('0.05'), Decimal('0.02')]
            current_referrer = user.referred_by
            
            for i, rate in enumerate(rates):
                if not current_referrer:
                    break
                
                # Le parrain ne touche la commission que s'il est lui-même VIP
                if current_referrer.vip_level and current_referrer.vip_level.price > 0:
                    commission = plan.price * rate
                    current_referrer.balance += commission
                    current_referrer.total_earnings += commission
                    current_referrer.save()
                    
                    Transaction.objects.create(
                        user=current_referrer,
                        from_user=user,
                        amount=commission,
                        transaction_type='REFERRAL_BONUS',
                        status='COMPLETED',
                        description=f"Com. Parrainage Niv {i+1} : {user.username} a acheté {plan.name}"
                    )
                
                # On remonte au parrain suivant
                current_referrer = current_referrer.referred_by
            # -----------------------------------------------------
        else:
            messages.error(request, "Solde insuffisant.")
    return redirect('vip_plans')

@login_required
def daily_check_in(request):
    if request.method == 'POST':
        today = timezone.now().date()
        user = request.user
        if user.last_check_in == today:
            messages.warning(request, "Déjà récupéré aujourd'hui.")
            return redirect('dashboard')
        yesterday = today - timezone.timedelta(days=1)
        user.check_in_streak = user.check_in_streak + 1 if user.last_check_in == yesterday else 1
        if user.check_in_streak > 7: user.check_in_streak = 1
        rewards = {1: 5, 2: 10, 3: 15, 4: 20, 5: 25, 6: 30, 7: 50}
        amount = Decimal(str(rewards.get(user.check_in_streak, 5)))
        user.balance += amount
        user.total_earnings += amount
        user.last_check_in = today
        user.save()
        Transaction.objects.create(user=user, amount=amount, transaction_type='DAILY_CHECKIN', status='COMPLETED', description=f"Bonus jour {user.check_in_streak}")
        update_mission_progress(user, 'CHECK_IN')
        award_xp(user, 10, "Check-in quotidien")
        messages.success(request, f"+{amount} FCFA !")
    return redirect('dashboard')

@login_required
def start_mining(request):
    if request.method == 'POST':
        if MiningSession.objects.filter(user=request.user, is_active=True).exists():
            messages.error(request, "Déjà en cours.")
        else:
            MiningSession.objects.create(
                user=request.user,
                end_time=timezone.now() + timezone.timedelta(hours=MiningSession.DURATION_HOURS)
            )
            update_mission_progress(request.user, 'MINE')
            if not request.user.has_triggered_referral_bonus and request.user.referred_by:
                now = timezone.now()
                hours_since_reg = (now - request.user.date_joined).total_seconds() / 3600
                if hours_since_reg >= 24:
                    referrer = request.user.referred_by
                    if referrer.vip_level and referrer.vip_level.price > 0:
                        bonus = referrer.vip_level.referral_reward
                        referrer.balance += bonus
                        referrer.free_spins += 1
                        referrer.save()
                        Transaction.objects.create(
                            user=referrer, 
                            from_user=request.user,
                            amount=bonus, 
                            transaction_type='REFERRAL_BONUS', 
                            status='COMPLETED', 
                            description=f"Bonus invitation: {request.user.username} (+1 tour de roue)"
                        )
                request.user.has_triggered_referral_bonus = True
                request.user.save()
            messages.success(request, "Minage lancé !")
    return redirect('dashboard')

@login_required
def claim_mining(request):
    if request.method == 'POST':
        session = MiningSession.objects.filter(user=request.user, is_active=True).first()
        if session and session.is_completed:
            user_level = request.user.vip_level or VIPLevel.objects.filter(price=0).first()
            amount = user_level.daily_mining_reward
            now = timezone.now()
            if request.user.turbo_mining_until and request.user.turbo_mining_until > now:
                amount *= 2
            request.user.balance += amount
            request.user.total_earnings += amount
            request.user.save()
            session.is_active = False
            session.is_claimed = True
            session.earned_amount = amount
            session.save()
            Transaction.objects.create(user=request.user, amount=amount, transaction_type='MINING_REWARD', status='COMPLETED', description=f"Gain minage {user_level.name}")
            award_xp(request.user, 15, "Minage terminé")
            from .utils import send_push_notification
            send_push_notification(request.user, "Minage terminé", f"+{amount} F gagnés ! Lancez une nouvelle session de 4h.", url=reverse('mining'))
            messages.success(request, f"Gain de {amount} FCFA réclamé !")
    return redirect('dashboard')

@login_required
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def complete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user_level = request.user.vip_level or VIPLevel.objects.filter(price=0).first()
    today = timezone.now().date()
    if UserTaskCompletion.objects.filter(user=request.user, task=task, completed_at__date=today).exists():
        messages.warning(request, "Déjà soumis aujourd'hui.")
    elif UserTaskCompletion.objects.filter(user=request.user, completed_at__date=today).count() >= user_level.daily_task_limit + request.user.extra_tasks_today:
        messages.error(request, "Limite atteinte.")
    else:
        screenshot = request.FILES.get('screenshot')
        proof_link = request.POST.get('proof_link')
        
        if task.requires_link_proof and not proof_link:
            messages.error(request, "Veuillez fournir le lien de votre profil ou de la page.")
            return redirect('tasks')
            
        if not screenshot:
            messages.error(request, "Capture manquante.")
        elif screenshot.size > 5 * 1024 * 1024:
            messages.error(request, "Fichier trop volumineux. Maximum 5 Mo.")
        elif not validate_image_magic_bytes(screenshot):
            messages.error(request, "Format de fichier non supporté ou fichier corrompu.")
        else:
            img_hash = compute_phash(screenshot)

            existing_hashes = UserTaskCompletion.objects.exclude(
                image_hash__isnull=True
            ).exclude(image_hash='').values_list('image_hash', flat=True)

            for existing in existing_hashes:
                if len(existing) == 16 and hamming_distance(img_hash, existing) <= 10:
                    messages.error(request, "Cette capture est trop similaire à une preuve déjà soumise.")
                    return redirect('tasks')

            UserTaskCompletion.objects.create(
                user=request.user, 
                task=task, 
                screenshot=screenshot, 
                proof_link=proof_link,
                image_hash=img_hash,
                status='PENDING'
            )
            update_mission_progress(request.user, 'COMPLETE_TASKS')
            messages.success(request, "Preuve envoyée, en attente de validation.")
    return redirect('tasks')

@login_required
def start_auto_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, is_automatic=True)
    user_level = request.user.vip_level or VIPLevel.objects.filter(price=0).first()
    today = timezone.now().date()

    if UserTaskCompletion.objects.filter(user=request.user, task=task, completed_at__date=today).exists():
        messages.warning(request, "Tâche déjà validée pour aujourd'hui.")
        return redirect('tasks')

    if UserTaskCompletion.objects.filter(user=request.user, completed_at__date=today).count() >= user_level.daily_task_limit + request.user.extra_tasks_today:
        messages.error(request, "Limite de tâches atteinte.")
        return redirect('tasks')

    # On crée une complétion en attente pour marquer le début
    # On utilise le statut 'PENDING' pour indiquer que le timer a commencé
    completion, created = UserTaskCompletion.objects.get_or_create(
        user=request.user,
        task=task,
        status='PENDING',
        defaults={'completed_at': timezone.now()}
    )

    context = {
        'task': task,
        'duration': task.duration_seconds,
        'completion_id': completion.id
    }
    return render(request, 'core/task_timer.html', context)

@login_required
def claim_auto_task(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id, is_automatic=True)
        completion = UserTaskCompletion.objects.filter(
            user=request.user, 
            task=task, 
            status='PENDING'
        ).last()

        if not completion:
            messages.error(request, "Session de tâche invalide.")
            return redirect('tasks')

        # Vérification du temps écoulé (sécurité côté serveur)
        elapsed = (timezone.now() - completion.completed_at).total_seconds()
        if elapsed < task.duration_seconds - 2: # Marge de 2s pour la latence réseau
            messages.error(request, "Temps insuffisant. Veuillez patienter.")
            return redirect('tasks')

        user_level = request.user.vip_level or VIPLevel.objects.filter(price=0).first()
        reward = user_level.task_reward_rate

        completion.status = 'PENDING'
        completion.save()

        Transaction.objects.create(
            user=request.user,
            amount=reward,
            transaction_type='TASK_REWARD',
            status='COMPLETED',
            description=f"Gain Timer : {task.title}"
        )
        messages.success(request, f"Tâche terminée ! En attente de validation par l'admin.")

    return redirect('tasks')

@login_required
def finish_onboarding(request):
    if request.method == 'POST':
        request.user.has_seen_onboarding = True
        request.user.save()
        return JsonResponse({'success': True})
    return redirect('dashboard')
@login_required
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def deposit_view(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        sender_phone = request.POST.get('sender_phone')
        reference = request.POST.get('reference')
        proof_image = request.FILES.get('proof_image')
        
        from .utils import validate_image_magic_bytes

        if not proof_image or not sender_phone or not reference:
            messages.error(request, "Veuillez remplir tous les champs et fournir la preuve.")
            return redirect('deposit')

        if proof_image.size > 5 * 1024 * 1024:
            messages.error(request, "Fichier trop volumineux. Maximum 5 Mo.")
            return redirect('deposit')

        if not validate_image_magic_bytes(proof_image):
            messages.error(request, "Format de fichier non supporté ou fichier corrompu.")
            return redirect('deposit')

        try:
            deposit_amount = int(amount)
        except (ValueError, TypeError):
            messages.error(request, "Montant invalide.")
            return redirect('deposit')

        if deposit_amount >= 500:
            Transaction.objects.create(
                user=request.user, 
                amount=Decimal(str(deposit_amount)), 
                transaction_type='DEPOSIT', 
                status='PENDING', 
                payment_method=request.POST.get('payment_method'), 
                reference_id=reference,
                proof_image=proof_image,
                description=f"Dépôt de {deposit_amount} F via {sender_phone} (Ref: {reference})"
            )
            messages.success(request, "Dépôt en attente de validation.")
            return redirect('dashboard')
    
    deposit_methods = DepositMethod.objects.filter(is_active=True)
    return render(request, 'core/depot_reward.html', {'deposit_methods': deposit_methods})

@login_required
@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def withdraw_view(request):
    user = request.user
    
    # SÉCURITÉ : Seuls les VIP peuvent retirer
    if not user.vip_level or user.vip_level.price == 0:
        messages.error(request, "Le retrait est réservé aux membres VIP. Veuillez activer un pack pour débloquer cette fonctionnalité.")
        return redirect('vip_plans')

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except Exception:
            amount = Decimal('0')

        if amount < Decimal('1000'):
            messages.error(request, "Montant minimum de retrait : 1 000 F.")
            return redirect('withdraw')

        with transaction.atomic():
            user = CustomUser.objects.select_for_update().get(id=request.user.id)

            today = timezone.now().date()
            today_withdrawals = Transaction.objects.filter(
                user=user, transaction_type='WITHDRAWAL', status__in=['PENDING', 'COMPLETED'],
                created_at__date=today
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            if today_withdrawals + amount > Decimal('50000'):
                messages.error(request, "Limite de retrait journalière de 50 000 F atteinte.")
                return redirect('withdraw')

            phone_number = request.POST.get('phone_number')

            if user.withdrawal_phone_locked and user.withdrawal_phone_locked != phone_number:
                messages.error(request, f"Accès refusé. Vos retraits sont verrouillés sur le numéro {user.withdrawal_phone_locked}. Contactez le support.")
                return redirect('withdraw')

            if user.balance < amount:
                messages.error(request, "Solde insuffisant.")
                return redirect('withdraw')

            if not user.withdrawal_phone_locked:
                user.withdrawal_phone_locked = phone_number

            user.balance -= amount
            user.save()

            Transaction.objects.create(
                user=user, amount=amount, transaction_type='WITHDRAWAL',
                status='PENDING', payment_method=request.POST.get('payment_method'),
                description=f"Retrait vers {phone_number}"
            )

            messages.success(request, "Demande envoyée. Votre numéro de retrait est désormais verrouillé.")
            return redirect('dashboard')
    return render(request, 'core/retrait_reward.html')

# --- ESPACE ADMIN ---

class AdminLoginView(LoginView):
    template_name = 'core/admin/login.html'
    redirect_authenticated_user = False # On désactive la redirection automatique
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect('/management/')
            else:
                messages.error(request, "Accès refusé. Vous n'avez pas les droits administrateur.")
                return redirect('dashboard')
        return super().get(request, *args, **kwargs)
    
    def get_success_url(self):
        return '/management/'

@staff_member_required(login_url='/management/login/')
def admin_dashboard(request):
    try:
        today = timezone.now().date()
        yesterday = timezone.now() - timezone.timedelta(days=1)
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        
        # Statistiques 24h
        deposits_24h = Transaction.objects.filter(transaction_type='DEPOSIT', status='COMPLETED', created_at__gte=yesterday).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        withdrawals_24h = Transaction.objects.filter(transaction_type='WITHDRAWAL', status='COMPLETED', created_at__gte=yesterday).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        vip_sales_24h = Transaction.objects.filter(transaction_type='VIP_PURCHASE', status='COMPLETED', created_at__gte=yesterday).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Totaux globaux
        total_deposits = Transaction.objects.filter(transaction_type='DEPOSIT', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_withdrawals = Transaction.objects.filter(transaction_type='WITHDRAWAL', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_vip = Transaction.objects.filter(transaction_type='VIP_PURCHASE', status='COMPLETED').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Utilisateurs
        total_users = CustomUser.objects.count()
        new_users_7d = CustomUser.objects.filter(created_at__gte=seven_days_ago).count()
        users_today = CustomUser.objects.filter(created_at__date=today).count()
        active_vips = CustomUser.objects.filter(vip_level__price__gt=0, vip_expiry_date__gte=timezone.now()).count()
        
        # Graphique 7 jours : inscriptions
        daily_users = []
        daily_revenue = []
        daily_labels = []
        for i in range(6, -1, -1):
            day = timezone.now() - timezone.timedelta(days=i)
            daily_labels.append(day.strftime('%d/%m'))
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timezone.timedelta(days=1)
            daily_users.append(CustomUser.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count())
            rev = Transaction.objects.filter(
                transaction_type__in=['DEPOSIT', 'VIP_PURCHASE'],
                status='COMPLETED',
                created_at__gte=day_start, created_at__lt=day_end
            ).aggregate(total=Sum('amount'))['total'] or 0
            daily_revenue.append(float(rev))
        
        # Transactions par type
        tx_counts = Transaction.objects.values('transaction_type').annotate(total=Sum('amount')).filter(status='COMPLETED')
        tx_by_type = {t['transaction_type']: float(t['total']) for t in tx_counts}
        
        # Niveaux VIP
        vip_counts = list(VIPLevel.objects.annotate(count=Count('customuser')).values('name', 'count', 'price'))
        
        context = {
            'pending_deposits': Transaction.objects.filter(transaction_type='DEPOSIT', status='PENDING'),
            'pending_withdrawals': Transaction.objects.filter(transaction_type='WITHDRAWAL', status='PENDING'),
            'net_platform_balance': total_deposits - total_withdrawals,
            'net_profit_24h': deposits_24h + vip_sales_24h - withdrawals_24h,
            'total_deposited': total_deposits,
            'total_withdrawn': total_withdrawals,
            'total_vip': total_vip,
            'total_users': total_users,
            'new_users_7d': new_users_7d,
            'users_today': users_today,
            'active_vips': active_vips,
            'chart_labels': json.dumps(daily_labels),
            'chart_users': json.dumps(daily_users),
            'chart_revenue': json.dumps(daily_revenue),
            'tx_by_type': json.dumps(tx_by_type),
            'vip_counts': vip_counts,
        }
        return render(request, 'core/admin/dashboard.html', context)
    except Exception as e:
        return HttpResponse(f"Erreur : {str(e)}", status=500)

@staff_member_required(login_url='/management/login/')
def admin_manage_transactions(request, type):
    tx_type = 'DEPOSIT' if type == 'deposits' else 'WITHDRAWAL'
    transactions = Transaction.objects.filter(transaction_type=tx_type).order_by('-created_at')
    return render(request, 'core/admin/transactions.html', {'transactions': transactions, 'type': type})

@staff_member_required(login_url='/management/login/')
def admin_update_transaction(request, tx_id, action):
    tx = get_object_or_404(Transaction, id=tx_id)
    if tx.status == 'PENDING':
        if action == 'approve':
            if tx.transaction_type == 'DEPOSIT':
                tx.user.balance += tx.amount
                tx.user.total_earnings += tx.amount
                tx.user.is_verified = True
                tx.user.save()
                award_xp(tx.user, 30, f"Dépôt de {tx.amount} F")
                Notification.objects.create(user=tx.user, title="Dépôt Validé", message=f"Votre dépôt de {tx.amount} F a été approuvé.")
            tx.status = 'COMPLETED'
        elif action == 'reject':
            if tx.transaction_type == 'WITHDRAWAL':
                tx.user.balance += tx.amount
                tx.user.save()
            tx.status = 'REJECTED'
        tx.save()
    return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))

@staff_member_required(login_url='/management/login/')
def admin_manage_users(request):
    query = request.GET.get('q')
    if query:
        users = CustomUser.objects.filter(
            models.Q(username__icontains=query) | 
            models.Q(phone_number__icontains=query)
        ).order_by('-date_joined')
    else:
        users = CustomUser.objects.all().order_by('-date_joined')
    
    suspicious_ips = CustomUser.objects.values('last_ip').annotate(count=Count('id')).filter(count__gt=1)
    
    return render(request, 'core/admin/users.html', {
        'users': users,
        'suspicious_count': suspicious_ips.count(),
        'query': query
    })

@staff_member_required(login_url='/management/login/')
def admin_ban_user(request, user_id):
    target_user = get_object_or_404(CustomUser, id=user_id)
    if not target_user.is_staff:
        target_user.is_active = False
        target_user.save()
        messages.warning(request, f"L'utilisateur {target_user.username} a été banni.")
    return redirect('admin_users')

@staff_member_required(login_url='/management/login/')
def admin_export_withdrawals(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="retraits_en_attente.csv"'
    writer = csv.writer(response)
    writer.writerow(['Utilisateur', 'Téléphone', 'Montant', 'Méthode', 'Date'])
    withdrawals = Transaction.objects.filter(transaction_type='WITHDRAWAL', status='PENDING')
    for w in withdrawals:
        writer.writerow([w.user.username, w.user.phone_number, w.amount, w.get_payment_method_display(), w.created_at.strftime('%d/%m/%Y %H:%M')])
    return response

@staff_member_required(login_url='/management/login/')
def admin_quick_edit_balance(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        amount = Decimal(request.POST.get('amount', '0'))
        action = request.POST.get('action')
        
        if action == 'add':
            user.balance += amount
            Transaction.objects.create(
                user=user, amount=amount, transaction_type='DEPOSIT',
                status='COMPLETED', description=f"Ajustement admin: +{amount} F"
            )
            messages.success(request, f"{amount} F ajoutés à {user.username}")
        elif action == 'sub':
            user.balance -= amount
            Transaction.objects.create(
                user=user, amount=amount, transaction_type='WITHDRAWAL',
                status='COMPLETED', description=f"Ajustement admin: -{amount} F"
            )
            messages.warning(request, f"{amount} F retirés à {user.username}")
        
        user.save()
    return redirect('admin_users')

@staff_member_required(login_url='/management/login/')
def admin_review_tasks(request):
    return render(request, 'core/admin/review_tasks.html', {'completions': UserTaskCompletion.objects.filter(status='PENDING').order_by('-completed_at')})

@staff_member_required(login_url='/management/login/')
def admin_update_task_status(request, completion_id, action):
    completion = get_object_or_404(UserTaskCompletion, id=completion_id)
    if completion.status == 'PENDING':
        reward = (completion.user.vip_level or VIPLevel.objects.filter(price=0).first()).task_reward_rate
        if action == 'approve':
            completion.status = 'APPROVED'
            completion.user.balance += reward
            completion.user.total_earnings += reward
            completion.user.save()
            Transaction.objects.create(user=completion.user, amount=reward, transaction_type='TASK_REWARD', status='COMPLETED', description=f"Tâche validée : {completion.task.title}")
            award_xp(completion.user, 20, f"Tâche : {completion.task.title}")
            Notification.objects.create(user=completion.user, title="Tâche Validée", message=f"+{reward} F pour {completion.task.title}")
        else:
            completion.status = 'REJECTED'
            Notification.objects.create(user=completion.user, title="Tâche Refusée", message=f"Preuve pour {completion.task.title} rejetée.")
        completion.save()
    return redirect('admin_review_tasks')

@staff_member_required(login_url='/management/login/')
def admin_manage_deposit_methods(request):
    methods = DepositMethod.objects.all().order_by('operator')
    return render(request, 'core/admin/manage_deposit.html', {'methods': methods})

@staff_member_required(login_url='/management/login/')
def admin_add_deposit_method(request):
    if request.method == 'POST':
        operator = request.POST.get('operator')
        name = request.POST.get('name')
        number = request.POST.get('number')
        
        if operator and name and number:
            DepositMethod.objects.create(operator=operator, name=name, number=number)
            messages.success(request, "Méthode de dépôt ajoutée !")
        else:
            messages.error(request, "Tous les champs sont obligatoires.")
            
    return redirect('admin_manage_deposit_methods')

@staff_member_required(login_url='/management/login/')
def admin_delete_deposit_method(request, method_id):
    method = get_object_or_404(DepositMethod, id=method_id)
    method.delete()
    messages.success(request, "Méthode de dépôt supprimée !")
    return redirect('admin_manage_deposit_methods')

@login_required
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def verify_phone_view(request):
    if request.user.is_phone_verified:
        return redirect('dashboard')
        
    if request.method == 'POST':
        code = request.POST.get('otp_code')
        user = request.user
        if user.otp_code and user.otp_created_at and check_password(code, user.otp_code):
            if timezone.now() - user.otp_created_at > timezone.timedelta(minutes=10):
                messages.error(request, "Code expiré. Veuillez redemander.")
                return redirect('verify_phone')
            user.is_phone_verified = True
            user.otp_code = None
            user.otp_created_at = None
            user.save()
            messages.success(request, "Numéro vérifié avec succès !")
            return redirect('dashboard')
        else:
            messages.error(request, "Code incorrect. Veuillez réessayer.")
            
    return render(request, 'core/verify_phone.html')

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def forgot_password_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        user = CustomUser.objects.filter(phone_number=phone).first()
        if user:
            raw_otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.otp_code = make_password(raw_otp)
            user.otp_created_at = timezone.now()
            user.save()
            messages.success(request, "Un code de réinitialisation a été généré. Veuillez contacter le bot Telegram.")
            request.session['reset_phone'] = phone
            return redirect('reset_password')
        else:
            messages.error(request, "Numéro non trouvé.")
    return render(request, 'core/forgot_password.html')

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def reset_password_view(request):
    phone = request.session.get('reset_phone')
    if not phone:
        messages.error(request, "Session expirée. Veuillez recommencer.")
        return redirect('forgot_password')
    user = get_object_or_404(CustomUser, phone_number=phone)
    if request.method == 'POST':
        code = request.POST.get('otp_code')
        new_password = request.POST.get('new_password')
        if user.otp_code and user.otp_created_at and check_password(code, user.otp_code):
            if timezone.now() - user.otp_created_at > timezone.timedelta(minutes=10):
                messages.error(request, "Code expiré. Veuillez recommencer.")
                return redirect('forgot_password')
            user.set_password(new_password)
            user.otp_code = None
            user.otp_created_at = None
            user.save()
            del request.session['reset_phone']
            messages.success(request, "Mot de passe réinitialisé avec succès !")
            return redirect('login')
        else:
            messages.error(request, "Code incorrect.")
    return render(request, 'core/reset_password.html')

@login_required
def notification_count_view(request):
    count = request.user.notifications.filter(is_read=False).count()
    return HttpResponse(f'{count}' if count > 0 else "")

def cgu_view(request):
    return render(request, 'core/cgu.html')

def privacy_view(request):
    return render(request, 'core/privacy.html')

@login_required
def support_view(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        if subject and message:
            SupportTicket.objects.create(user=request.user, subject=subject, message=message)
            messages.success(request, "Votre ticket a été envoyé. Un administrateur vous répondra bientôt.")
            return redirect('support')
            
    tickets = request.user.tickets.all().order_by('-created_at')
    return render(request, 'core/support.html', {'tickets': tickets})

@staff_member_required(login_url='/management/login/')
def admin_support_view(request):
    tickets = SupportTicket.objects.all().order_by('-created_at')
    return render(request, 'core/admin/support_manage.html', {'tickets': tickets})

@staff_member_required(login_url='/management/login/')
def admin_reply_ticket(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        reply = request.POST.get('reply')
        status = request.POST.get('status', 'CLOSED')
        if reply:
            ticket.admin_reply = reply
            ticket.status = status
            ticket.save()
            
            # Notification à l'utilisateur
            Notification.objects.create(
                user=ticket.user,
                title="Réponse au Support",
                message=f"L'admin a répondu à votre ticket : {ticket.subject}"
            )
            messages.success(request, "Réponse envoyée !")
            
    return redirect('admin_support')

import io
import qrcode
from django.http import HttpResponse
from django.urls import reverse

def qr_code_view(request, code):
    qr = qrcode.make(f"{request.scheme}://{request.get_host()}{reverse('register')}?ref={code}")
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    buf.seek(0)
    return HttpResponse(buf.getvalue(), content_type='image/png')

@staff_member_required(login_url='/management/login/')
def admin_announcements(request):
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'core/admin/announcements.html', {'announcements': announcements})

@staff_member_required(login_url='/management/login/')
def admin_add_announcement(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        link = request.POST.get('link', '')
        if title and message:
            Announcement.objects.create(title=title, message=message, link=link or None)
            messages.success(request, "Annonce créée.")
        else:
            messages.error(request, "Titre et message requis.")
        return redirect('admin_announcements')
    return render(request, 'core/admin/add_announcement.html')

@staff_member_required(login_url='/management/login/')
def admin_toggle_announcement(request, ann_id):
    ann = get_object_or_404(Announcement, id=ann_id)
    ann.is_active = not ann.is_active
    ann.save()
    return redirect('admin_announcements')

@staff_member_required(login_url='/management/login/')
def admin_delete_announcement(request, ann_id):
    ann = get_object_or_404(Announcement, id=ann_id)
    ann.delete()
    return redirect('admin_announcements')

@login_required
@require_POST
def theme_api_view(request):
    theme = request.POST.get('theme', 'dark')
    request.user.dark_mode = (theme == 'dark')
    request.user.save(update_fields=['dark_mode'])
    return JsonResponse({'ok': True})