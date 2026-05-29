from django.urls import path
from . import views

urlpatterns = [
    # Pages Publiques
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-phone/', views.verify_phone_view, name='verify_phone'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    
    # Dashboard et Sous-pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('survey/', views.survey_view, name='survey'),
    path('submit-survey/', views.submit_survey, name='submit_survey'),
    path('tasks/', views.tasks_view, name='tasks'),
    path('mining/', views.mining_view, name='mining'),
    path('team/', views.team_view, name='team'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('profile/', views.profile_view, name='profile'),
    path('communaute/', views.communaute_view, name='communaute'),
    path('wallet/', views.wallet_view, name='wallet'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/unread-count/', views.notification_count_view, name='unread_notifications_count'),
    path('faq/', views.faq_view, name='faq'),
    path('support/', views.support_view, name='support'),
    path('cgu/', views.cgu_view, name='cgu'),
    path('privacy/', views.privacy_view, name='privacy'),
    
    # Plans VIP
    path('vip-plans/', views.vip_plans_view, name='vip_plans'),
    path('buy-vip/<int:plan_id>/', views.buy_vip, name='buy_vip'),

    # Boosts
    path('boosts/', views.boosts_view, name='boosts'),
    path('buy-boost/<int:boost_id>/', views.buy_boost, name='buy_boost'),

    # Parrainage
    path('referral-program/', views.referral_program_view, name='referral_program'),
    
    # Finance
    path('deposit/', views.deposit_view, name='deposit'),
    path('withdraw/', views.withdraw_view, name='withdraw'),
    
    # Actions
    path('start-mining/', views.start_mining, name='start_mining'),
    path('claim-mining/', views.claim_mining, name='claim_mining'),
    path('daily-check-in/', views.daily_check_in, name='daily_check_in'),
    path('wheel/', views.wheel_view, name='wheel'),
    path('spin-wheel/', views.spin_wheel, name='spin_wheel'),
    path('complete-task/<int:task_id>/', views.complete_task, name='complete_task'),
    path('start-auto-task/<int:task_id>/', views.start_auto_task, name='start_auto_task'),
    path('claim-auto-task/<int:task_id>/', views.claim_auto_task, name='claim_auto_task'),
    path('finish-onboarding/', views.finish_onboarding, name='finish_onboarding'),

    # --- ROUTES ADMIN PERSONNALISÉES ---
    path('management/login/', views.AdminLoginView.as_view(), name='admin_login'),
    path('management/', views.admin_dashboard, name='admin_dashboard'),
    path('management/transactions/<str:type>/', views.admin_manage_transactions, name='admin_transactions'),
    path('management/tx-update/<int:tx_id>/<str:action>/', views.admin_update_transaction, name='admin_tx_update'),
    path('management/support/', views.admin_support_view, name='admin_support'),
    path('management/support/reply/<int:ticket_id>/', views.admin_reply_ticket, name='admin_reply_ticket'),
    path('management/users/', views.admin_manage_users, name='admin_users'),
    path('management/export-withdrawals/', views.admin_export_withdrawals, name='admin_export_withdrawals'),
    path('management/user-edit/<int:user_id>/', views.admin_quick_edit_balance, name='admin_user_edit'),
    path('management/user-ban/<int:user_id>/', views.admin_ban_user, name='admin_ban_user'),
    path('management/tasks-review/', views.admin_review_tasks, name='admin_review_tasks'),
    path('management/task-update/<int:completion_id>/<str:action>/', views.admin_update_task_status, name='admin_task_update'),
    path('management/tasks/', views.admin_manage_tasks, name='admin_manage_tasks'),
    path('management/tasks/add/', views.admin_add_task, name='admin_task_add'),
    path('management/tasks/edit/<int:task_id>/', views.admin_edit_task, name='admin_task_edit'),
    path('management/deposits/', views.admin_manage_deposit_methods, name='admin_manage_deposit_methods'),
    path('management/deposits/add/', views.admin_add_deposit_method, name='admin_deposit_add'),
    path('management/deposits/delete/<int:method_id>/', views.admin_delete_deposit_method, name='admin_deposit_delete'),

    path('management/vip/', views.admin_manage_vip, name='admin_manage_vip'),
    path('management/vip/add/', views.admin_add_vip, name='admin_vip_add'),
    path('management/vip/edit/<int:vip_id>/', views.admin_edit_vip, name='admin_vip_edit'),
    path('management/vip/delete/<int:vip_id>/', views.admin_delete_vip, name='admin_vip_delete'),
]
