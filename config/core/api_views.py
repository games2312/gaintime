from decimal import Decimal

from django.db import connection
from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CustomUser, DepositMethod, Task, Transaction, VIPLevel


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_ok = True
    except Exception:
        db_ok = False
    status_code = 200 if db_ok else 500
    return JsonResponse({
        'status': 'ok' if db_ok else 'error',
        'database': 'ok' if db_ok else 'error',
    }, status=status_code)


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'phone_number', 'balance', 'total_earnings',
                  'vip_level', 'vip_expiry_date', 'invitation_code',
                  'is_phone_verified', 'check_in_streak', 'free_spins']


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'platform', 'category',
                  'link', 'reward_amount', 'duration_seconds', 'is_automatic',
                  'requires_link_proof', 'is_active']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'transaction_type', 'status',
                  'payment_method', 'description', 'created_at']


class VIPLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = VIPLevel
        fields = ['id', 'name', 'price', 'daily_mining_reward',
                  'daily_task_limit', 'task_reward_rate', 'referral_reward',
                  'validity_days', 'image']


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user)
        return Response(serializer.data)


class LeaderboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        top = CustomUser.objects.filter(is_active=True) \
            .order_by('-total_earnings')[:50]
        data = [{'username': u.username, 'total_earnings': float(u.total_earnings),
                 'vip': u.vip_level.name if u.vip_level else 'Gratuit'}
                for u in top]
        return Response(data)


class TaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Task.objects.filter(is_active=True)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class VIPLevelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VIPLevel.objects.all().order_by('price')
    serializer_class = VIPLevelSerializer
    permission_classes = [permissions.AllowAny]


class DepositMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepositMethod
        fields = ['operator', 'name', 'number']


class DepositMethodView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        methods = DepositMethod.objects.filter(is_active=True)
        serializer = DepositMethodSerializer(methods, many=True)
        return Response(serializer.data)
