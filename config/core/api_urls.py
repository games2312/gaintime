from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api_views

router = DefaultRouter()
router.register(r'tasks', api_views.TaskViewSet, basename='api_tasks')
router.register(r'transactions', api_views.TransactionViewSet, basename='api_transactions')
router.register(r'vip-plans', api_views.VIPLevelViewSet, basename='api_vip_plans')

urlpatterns = [
    path('health/', api_views.health_check, name='api_health'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', api_views.MeView.as_view(), name='api_me'),
    path('leaderboard/', api_views.LeaderboardView.as_view(), name='api_leaderboard'),
    path('deposit-methods/', api_views.DepositMethodView.as_view(), name='api_deposit_methods'),
] + router.urls
