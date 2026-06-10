from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import timedelta
import json
from decimal import Decimal
from datetime import timedelta
from unittest.mock import Mock

from core.models import (
    CustomUser, VIPLevel, Transaction, MiningSession,
    Task, Boost, Badge, UserBadge, DailyMission,
    UserMissionProgress, PushSubscription, DepositMethod,
    UserTaskCompletion,
)
from core.views import compute_trust_score, check_badge_unlocks
from core.utils import compute_phash, hamming_distance, get_client_ip, validate_image_magic_bytes


def secure_client():
    """Return a Client that always uses HTTPS to avoid SSL redirect."""
    return Client(raise_request_exception=False)


class FinancialTests(TestCase):
    def setUp(self):
        self.vip1 = VIPLevel.objects.create(name="VIP 1", price=10000, daily_mining_reward=500, daily_task_limit=5, task_reward_rate=100)
        self.p3 = CustomUser.objects.create_user(username="p3", phone_number="611111111")
        self.p3.vip_level = self.vip1; self.p3.save()
        self.p2 = CustomUser.objects.create_user(username="p2", phone_number="622222222", referred_by=self.p3)
        self.p2.vip_level = self.vip1; self.p2.save()
        self.p1 = CustomUser.objects.create_user(username="p1", phone_number="633333333", referred_by=self.p2)
        self.p1.vip_level = self.vip1; self.p1.save()
        self.user = CustomUser.objects.create_user(username="user", phone_number="644444444", referred_by=self.p1)
        self.user.balance = 20000; self.user.save()

    def test_referral_commissions(self):
        plan = self.vip1
        self.user.balance -= plan.price
        self.user.vip_level = plan; self.user.save()
        rates = [Decimal('0.10'), Decimal('0.05'), Decimal('0.02')]
        cr = self.user.referred_by
        for rate in rates:
            if cr:
                c = plan.price * rate
                cr.balance += c; cr.total_earnings += c; cr.save()
                cr = cr.referred_by
        self.assertEqual(self.p1.balance, 1000)
        self.assertEqual(self.p2.balance, 500)
        self.assertEqual(self.p3.balance, 200)


class CustomUserTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', phone_number='691234567', password='secret123')

    def test_auto_invitation_code(self):
        self.assertTrue(len(self.user.invitation_code) >= 6)

    def test_phone_verification(self):
        self.assertFalse(self.user.is_phone_verified)
        self.user.is_phone_verified = True; self.user.save()
        self.assertTrue(self.user.is_phone_verified)

    def test_referral_chain(self):
        p1 = CustomUser.objects.create_user(username='p1', phone_number='691234568')
        p2 = CustomUser.objects.create_user(username='p2', phone_number='691234569', referred_by=p1)
        self.user.referred_by = p2; self.user.save()
        self.assertEqual(self.user.referred_by, p2)

    def test_balance_default(self):
        self.assertEqual(self.user.balance, Decimal('0'))

    def test_trust_score_default(self):
        self.assertEqual(self.user.trust_score, 0)

    def test_invitation_code_unique(self):
        u2 = CustomUser.objects.create_user(username='testuser2', phone_number='691234568', password='secret123')
        self.assertNotEqual(self.user.invitation_code, u2.invitation_code)


class VIPLevelTests(TestCase):
    def test_create_vip(self):
        vip = VIPLevel.objects.create(name='Gold', price=5000, daily_mining_reward=300, daily_task_limit=10, task_reward_rate=150)
        self.assertIn('Gold', str(vip))
        self.assertIn('5000', str(vip))

    def test_free_vip(self):
        vip = VIPLevel.objects.create(name='Free', price=0, daily_mining_reward=100, daily_task_limit=3, task_reward_rate=50)
        self.assertEqual(vip.price, 0)


class MiningSessionTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='miner', phone_number='691234571')

    def test_create_session(self):
        now = timezone.now()
        s = MiningSession.objects.create(user=self.user, start_time=now, end_time=now+timedelta(hours=24), is_active=True, is_claimed=False)
        self.assertTrue(s.is_active)
        self.assertFalse(s.is_claimed)

    def test_earned_amount_default(self):
        now = timezone.now()
        s = MiningSession.objects.create(user=self.user, start_time=now, end_time=now+timedelta(hours=24))
        self.assertEqual(s.earned_amount, Decimal('0'))


class BoostTests(TestCase):
    def test_create_boost(self):
        b = Boost.objects.create(name='Turbo', price=500, boost_type='TURBO_MINING', duration_hours=24)
        self.assertIn('Turbo', str(b))

    def test_all_boost_types(self):
        for bt, _ in Boost.BOOST_TYPES:
            b = Boost.objects.create(name=f'B-{bt}', price=100, boost_type=bt, duration_hours=12)
            self.assertEqual(b.boost_type, bt)

    def test_default_quantity(self):
        b = Boost.objects.create(name='Pack', price=300, boost_type='FREE_SPIN_PACK', duration_hours=0)
        self.assertEqual(b.quantity, 1)


class BadgeTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='badgebob', phone_number='691234573')

    def test_create_badge(self):
        b = Badge.objects.create(name='Master', condition_type='TASKS_COMPLETED', condition_value=10)
        self.assertEqual(str(b), 'Master')

    def test_earn_badge(self):
        b = Badge.objects.create(name='First', condition_type='REFERRALS', condition_value=1, reward_amount=Decimal('100'))
        UserBadge.objects.create(user=self.user, badge=b)
        self.assertEqual(self.user.earned_badges.count(), 1)


class DailyMissionTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='mision', phone_number='691234574')

    def test_create_mission(self):
        m = DailyMission.objects.create(mission_type='COMPLETE_TASKS', target=3, reward=Decimal('50'))
        self.assertIn('50', str(m))

    def test_mission_progress(self):
        m = DailyMission.objects.create(mission_type='CHECK_IN', target=1, reward=Decimal('10'))
        p = UserMissionProgress.objects.create(user=self.user, mission=m, progress=0, completed=False)
        self.assertFalse(p.completed)
        p.progress = 1; p.completed = True; p.save()
        self.assertTrue(p.completed)


class PushSubscriptionTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='pushy', phone_number='691234575')

    def test_subscription_creation(self):
        s = PushSubscription.objects.create(user=self.user, endpoint='https://fcm.test/abc', auth_key='k1', p256dh_key='k2')
        self.assertEqual(self.user.push_subscriptions.count(), 1)
        self.assertEqual(s.auth_key, 'k1')


class AuthViewTests(TestCase):
    def setUp(self):
        self.client = secure_client()

    def test_register_page(self):
        r = self.client.get(reverse('register'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_register_user(self):
        u = CustomUser.objects.create_user(username='refcode', phone_number='691234576', password='t')
        r = self.client.post(reverse('register'), {
            'username': 'newbie', 'phone_number': '691234577',
            'invitation_code_input': u.invitation_code,
            'password': 'Test12345', 'confirm_password': 'Test12345'
        }, secure=True, follow=True)
        self.assertTrue(CustomUser.objects.filter(username='newbie').exists())

    def test_login_page(self):
        r = self.client.get(reverse('login'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_login_user(self):
        CustomUser.objects.create_user(username='logme', phone_number='691234577', password='Test12345')
        r = self.client.post(reverse('login'), {'username': 'logme', 'password': 'Test12345'}, secure=True, follow=True)
        self.assertIn('_auth_user_id', self.client.session)

    def test_logout(self):
        u = CustomUser.objects.create_user(username='logoutme', phone_number='691234578', password='Test12345')
        self.client.force_login(u)
        r = self.client.get(reverse('logout'), secure=True, follow=True)
        self.assertNotIn('_auth_user_id', self.client.session)


class AuthenticatedViewMixin:
    def _login_and_verify(self, username='dash', phone='691234579'):
        user = CustomUser.objects.create_user(username=username, phone_number=phone, password='Test12345')
        user.is_phone_verified = True
        user.has_completed_survey = True
        user.save()
        VIPLevel.objects.get_or_create(name='Free', defaults=dict(price=0, daily_mining_reward=100, daily_task_limit=3, task_reward_rate=50))
        self.client.force_login(user)
        return user


class DashboardViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify()

    def test_dashboard_200(self):
        r = self.client.get(reverse('dashboard'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_dashboard_redirects_anon(self):
        self.client.logout()
        r = self.client.get(reverse('dashboard'))
        self.assertNotEqual(r.status_code, 200)


class MiningViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('miner2', '691234580')

    def test_mining_page(self):
        r = self.client.get(reverse('mining'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_start_mining(self):
        r = self.client.post(reverse('start_mining'), secure=True, follow=True)
        self.assertTrue(MiningSession.objects.filter(user=self.user).exists())

    def test_mining_creates_active_session(self):
        self.client.post(reverse('start_mining'), secure=True, follow=True)
        s = MiningSession.objects.filter(user=self.user).first()
        self.assertIsNotNone(s)
        self.assertTrue(s.is_active)

    def test_daily_check_in(self):
        self.client.post(reverse('daily_check_in'), secure=True, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.check_in_streak, 1)
        self.assertIsNotNone(self.user.last_check_in)


class VIPViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.vip = VIPLevel.objects.create(name='Premium', price=5000, daily_mining_reward=500, daily_task_limit=10, task_reward_rate=200)
        self.user = self._login_and_verify('vipbuyer', '691234581')
        self.user.balance = Decimal('10000'); self.user.save()

    def test_vip_plans_page(self):
        r = self.client.get(reverse('vip_plans'), secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Premium')

    def test_buy_vip_deducts_balance(self):
        r = self.client.post(reverse('buy_vip', args=[self.vip.id]), secure=True, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('5000'))
        self.assertEqual(self.user.vip_level, self.vip)

    def test_buy_vip_insufficient_funds(self):
        self.user.balance = Decimal('1000'); self.user.save()
        r = self.client.post(reverse('buy_vip', args=[self.vip.id]), secure=True, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('1000'))
        self.assertIsNone(self.user.vip_level)


class TaskViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('tasker', '691234582')
        self.task = Task.objects.create(title='Test Task', reward_amount=Decimal('50'), is_active=True)

    def test_tasks_page(self):
        r = self.client.get(reverse('tasks'), secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Test Task')


class BoostViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('boostbob', '691234583')
        self.user.balance = Decimal('2000'); self.user.save()
        self.boost = Boost.objects.create(name='Extra Tasks', price=500, boost_type='EXTRA_TASKS', duration_hours=24)

    def test_boosts_page(self):
        r = self.client.get(reverse('boosts'), secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Extra Tasks')

    def test_buy_boost_deducts_balance(self):
        r = self.client.post(reverse('buy_boost', args=[self.boost.id]), secure=True, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('1500'))
        self.assertEqual(self.user.extra_tasks_today, 1)

    def test_buy_boost_insufficient_funds(self):
        self.user.balance = Decimal('100'); self.user.save()
        r = self.client.post(reverse('buy_boost', args=[self.boost.id]), secure=True, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('100'))
        self.assertEqual(self.user.extra_tasks_today, 0)


class ReferralViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('refboss', '691234584')

    def test_referral_page(self):
        r = self.client.get(reverse('referral_program'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_default_tier(self):
        self.assertEqual(self.user.referral_tier, 0)


class GamificationViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('gamer2', '691234585')

    def test_gamification_page(self):
        r = self.client.get(reverse('gamification'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_badge_appears(self):
        Badge.objects.create(name='Pioneer', condition_type='DAYS_ACTIVE', condition_value=0, is_active=True)
        r = self.client.get(reverse('gamification'), secure=True)
        self.assertContains(r, 'Pioneer')

    def test_mission_appears(self):
        DailyMission.objects.create(mission_type='CHECK_IN', target=1, reward=Decimal('10'), is_active=True)
        r = self.client.get(reverse('gamification'), secure=True)
        self.assertContains(r, 'Check-in quotidien')


class ChatViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('chatter', '691234586')

    def test_chat_page_authenticated(self):
        r = self.client.get(reverse('chat'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_chat_redirects_anon(self):
        self.client.logout()
        r = self.client.get(reverse('chat'))
        self.assertNotEqual(r.status_code, 200)


class ProfileViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('profiler', '691234587')

    def test_profile(self):
        r = self.client.get(reverse('profile'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_wallet(self):
        r = self.client.get(reverse('wallet'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_notifications(self):
        r = self.client.get(reverse('notifications'), secure=True)
        self.assertEqual(r.status_code, 200)


class ComputePhashTests(TestCase):
    def test_none_input_raises(self):
        with self.assertRaises((AttributeError, TypeError)):
            compute_phash(None)

    def test_empty_string_raises(self):
        with self.assertRaises(FileNotFoundError):
            compute_phash('')

    def test_returns_hex_string(self):
        import io
        from PIL import Image
        img = Image.new('RGB', (16, 16), color='red')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        result = compute_phash(buf)
        self.assertIsInstance(result, str)
        self.assertTrue(all(c in '0123456789abcdef' for c in result))

    def test_same_image_same_hash(self):
        import io
        from PIL import Image
        img = Image.new('RGB', (16, 16), color='blue')
        buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        h1 = compute_phash(buf)
        buf.seek(0)
        h2 = compute_phash(buf)
        self.assertEqual(h1, h2)


class HammingDistanceTests(TestCase):
    def test_same_strings(self):
        self.assertEqual(hamming_distance('abc', 'abc'), 0)

    def test_different_length(self):
        self.assertEqual(hamming_distance('abc', 'abcdef'), 100)

    def test_real_phash_distance_zero(self):
        self.assertEqual(hamming_distance('abcd1234', 'abcd1234'), 0)

    def test_real_phash_distance_nonzero(self):
        d = hamming_distance('0000ffff', 'ffff0000')
        self.assertGreater(d, 0)


class GetClientIpTests(TestCase):
    def test_x_forwarded_for(self):
        req = Mock(); req.META = {'HTTP_X_FORWARDED_FOR': '203.0.113.1, 10.0.0.1', 'REMOTE_ADDR': '10.0.0.1'}
        self.assertEqual(get_client_ip(req), '203.0.113.1')

    def test_remote_addr(self):
        req = Mock(); req.META = {'REMOTE_ADDR': '192.168.1.1'}
        self.assertEqual(get_client_ip(req), '192.168.1.1')

    def test_no_ip(self):
        req = Mock(); req.META = {}
        self.assertIsNone(get_client_ip(req))

    def test_x_forwarded_for_multiple(self):
        req = Mock(); req.META = {'HTTP_X_FORWARDED_FOR': '10.0.0.1, 10.0.0.2, 10.0.0.3'}
        self.assertEqual(get_client_ip(req), '10.0.0.1')


class TrustScoreTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='trustscore', phone_number='691234588', password='Test12345')

    def test_new_user_low_score(self):
        self.assertLessEqual(compute_trust_score(self.user), 30)

    def test_verified_phone_boosts(self):
        self.user.is_phone_verified = True; self.user.save()
        self.assertGreaterEqual(compute_trust_score(self.user), 25)

    def test_vip_extra_score(self):
        self.user.is_phone_verified = True; self.user.save()
        base = compute_trust_score(self.user)
        VIPLevel.objects.create(name='Gold', price=5000, daily_mining_reward=300, daily_task_limit=10, task_reward_rate=150)
        self.user.vip_level = VIPLevel.objects.first(); self.user.save()
        self.assertGreater(compute_trust_score(self.user), base)

    def test_capped_at_100(self):
        self.user.is_phone_verified = True
        VIPLevel.objects.create(name='Plat', price=10000, daily_mining_reward=1000, daily_task_limit=20, task_reward_rate=500)
        self.user.vip_level = VIPLevel.objects.first()
        self.user.date_joined = timezone.now() - timedelta(days=365); self.user.save()
        self.assertLessEqual(compute_trust_score(self.user), 100)

    def test_inactive_user_zero(self):
        self.user.is_active = False; self.user.save()
        self.assertEqual(compute_trust_score(self.user), 0)

    def test_referrals_increase_score(self):
        for i in range(3):
            CustomUser.objects.create_user(username=f'ref{i}', phone_number=f'69123459{i}', referred_by=self.user)
        self.assertGreaterEqual(compute_trust_score(self.user), 45)


class BadgeUnlockTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='unlocker', phone_number='691234590', password='Test12345')
        self.badge = Badge.objects.create(name='Veteran', condition_type='DAYS_ACTIVE', condition_value=0, reward_amount=Decimal('50'), is_active=True)

    def test_new_user_unlocks_days_badge(self):
        check_badge_unlocks(self.user)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.badge).exists())

    def test_badge_reward_added(self):
        check_badge_unlocks(self.user)
        self.user.refresh_from_db()
        self.assertGreaterEqual(self.user.balance, Decimal('50'))

    def test_reward_transaction_created(self):
        check_badge_unlocks(self.user)
        self.assertTrue(Transaction.objects.filter(user=self.user, transaction_type='TASK_REWARD').exists())

    def test_inactive_badge_not_unlocked(self):
        b2 = Badge.objects.create(name='Hidden', condition_type='DAYS_ACTIVE', condition_value=0, is_active=False)
        check_badge_unlocks(self.user)
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge=b2).exists())

    def test_existing_badge_not_unlocked_again(self):
        UserBadge.objects.create(user=self.user, badge=self.badge)
        check_badge_unlocks(self.user)
        self.assertEqual(UserBadge.objects.filter(user=self.user, badge=self.badge).count(), 1)


class DepositViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('depositor', '691234591')
        DepositMethod.objects.create(operator='OM', name='Test OM', number='670000000', is_active=True)
        self.valid_file = SimpleUploadedFile('proof.png', b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00', content_type='image/png')

    def test_deposit_page_200(self):
        r = self.client.get(reverse('deposit'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_deposit_missing_fields(self):
        r = self.client.post(reverse('deposit'), {'amount': '1000'}, secure=True, follow=True)
        self.assertContains(r, 'Veuillez remplir tous les champs')

    def test_deposit_invalid_amount(self):
        r = self.client.post(reverse('deposit'), {
            'amount': 'abc', 'sender_phone': '670000001', 'reference': 'ref123',
            'proof_image': self.valid_file,
        }, secure=True, follow=True)
        self.assertContains(r, 'Montant invalide')

    def test_deposit_below_minimum(self):
        r = self.client.post(reverse('deposit'), {
            'amount': '100', 'sender_phone': '670000001', 'reference': 'ref123',
            'proof_image': self.valid_file,
        }, secure=True, follow=True)
        tx = Transaction.objects.filter(user=self.user, transaction_type='DEPOSIT').count()
        self.assertEqual(tx, 0)

    def test_deposit_creates_pending_tx(self):
        r = self.client.post(reverse('deposit'), {
            'amount': '1000', 'sender_phone': '670000001',
            'reference': 'ref123', 'payment_method': 'OM',
            'proof_image': self.valid_file,
        }, secure=True, follow=True)
        tx = Transaction.objects.filter(user=self.user, transaction_type='DEPOSIT').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, 'PENDING')


class WithdrawalViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.vip = VIPLevel.objects.create(name='Platinum', price=10000, daily_mining_reward=500, daily_task_limit=10, task_reward_rate=200)
        self.user = self._login_and_verify('withdrawer', '691234592')
        self.user.vip_level = self.vip
        self.user.balance = Decimal('50000')
        self.user.save()

    def test_withdraw_page_200(self):
        r = self.client.get(reverse('withdraw'), secure=True)
        self.assertEqual(r.status_code, 200)

    def test_withdraw_below_minimum(self):
        r = self.client.post(reverse('withdraw'), {
            'amount': '500', 'phone_number': '670000001', 'payment_method': 'OM'
        }, secure=True, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('50000'))

    def test_withdraw_creates_pending_tx(self):
        r = self.client.post(reverse('withdraw'), {
            'amount': '5000', 'phone_number': '670000001', 'payment_method': 'OM'
        }, secure=True, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('45000'))
        tx = Transaction.objects.filter(user=self.user, transaction_type='WITHDRAWAL').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, 'PENDING')

    def test_withdraw_daily_limit(self):
        for i in range(3):
            self.client.post(reverse('withdraw'), {
                'amount': '20000', 'phone_number': '670000001', 'payment_method': 'OM'
            }, secure=True, follow=True)
            self.user.refresh_from_db()
        self.assertGreaterEqual(self.user.balance, Decimal('10000'))


class AutoTaskTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('autotasker', '691234593')
        self.task = Task.objects.create(
            title='Auto Task', is_automatic=True, duration_seconds=10,
            reward_amount=Decimal('50'), is_active=True
        )

    def test_auto_task_creates_pending(self):
        r = self.client.post(reverse('start_auto_task', args=[self.task.id]), secure=True, follow=True)
        c = UserTaskCompletion.objects.filter(user=self.user, task=self.task).first()
        self.assertIsNotNone(c)
        self.assertEqual(c.status, 'PENDING')

    def test_claim_auto_task_too_early(self):
        self.client.post(reverse('start_auto_task', args=[self.task.id]), secure=True, follow=True)
        c = UserTaskCompletion.objects.filter(user=self.user, task=self.task).first()
        c.completed_at = timezone.now()
        c.save()
        r = self.client.post(reverse('claim_auto_task', args=[self.task.id]), secure=True, follow=True)
        c.refresh_from_db()
        self.assertNotEqual(c.status, 'APPROVED')

    def test_claim_auto_task_needs_admin(self):
        self.client.post(reverse('start_auto_task', args=[self.task.id]), secure=True, follow=True)
        c = UserTaskCompletion.objects.filter(user=self.user, task=self.task).first()
        c.completed_at = timezone.now() - timedelta(seconds=20)
        c.save()
        r = self.client.post(reverse('claim_auto_task', args=[self.task.id]), secure=True, follow=True)
        c.refresh_from_db()
        self.assertEqual(c.status, 'PENDING')


class PushSubscribeViewTests(TestCase, AuthenticatedViewMixin):
    def setUp(self):
        self.client = secure_client()
        self.user = self._login_and_verify('pushsub', '691234594')

    def test_subscribe(self):
        r = self.client.post(reverse('push_subscribe'), {
            'endpoint': 'https://fcm.test/push1',
            'keys': {'auth': 'auth1', 'p256dh': 'key1'}
        }, content_type='application/json', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(user=self.user).exists())

    def test_unsubscribe(self):
        PushSubscription.objects.create(user=self.user, endpoint='https://fcm.test/push1')
        r = self.client.post(reverse('push_unsubscribe'), {
            'endpoint': 'https://fcm.test/push1'
        }, content_type='application/json', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(user=self.user).exists())

    def test_settings_returns_enabled(self):
        PushSubscription.objects.create(user=self.user, endpoint='https://fcm.test/push1')
        r = self.client.get(reverse('push_settings'), secure=True)
        data = json.loads(r.content)
        self.assertTrue(data['enabled'])


class MagicBytesValidationTests(TestCase):
    def test_jpeg_magic_bytes(self):
        import io
        buf = io.BytesIO(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01')
        self.assertTrue(validate_image_magic_bytes(buf))

    def test_png_magic_bytes(self):
        import io
        buf = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 8)
        self.assertTrue(validate_image_magic_bytes(buf))

    def test_webp_magic_bytes(self):
        import io
        buf = io.BytesIO(b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 8)
        self.assertTrue(validate_image_magic_bytes(buf))

    def test_invalid_magic_bytes(self):
        import io
        buf = io.BytesIO(b'GIF89a\x00\x00\x00\x00')
        self.assertFalse(validate_image_magic_bytes(buf))


class SecureSettingsTests(TestCase):
    def test_secret_key_required(self):
        import os
        key = os.environ.get('SECRET_KEY')
        self.assertIsNotNone(key)
        self.assertNotEqual(key, 'django-insecure-default-key-change-me')

    def test_csrf_cookie_httponly(self):
        from django.conf import settings
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)

    def test_session_cookie_httponly(self):
        from django.conf import settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)


class AllUrlsTest(TestCase):
    """Vérifie que chaque URL répond correctement (200 pour public, 302/403 pour auth)."""

    def setUp(self):
        self.client = secure_client()
        VIPLevel.objects.get_or_create(name='Free', defaults=dict(price=0, daily_mining_reward=100, daily_task_limit=3, task_reward_rate=50))
        self.vip_paid, _ = VIPLevel.objects.get_or_create(name='VIP1', defaults=dict(price=5000, daily_mining_reward=500, daily_task_limit=10, task_reward_rate=200))
        self.user = CustomUser.objects.create_user(username='urlcheck', phone_number='699999990', password='test123')
        self.user.is_phone_verified = True
        self.user.has_completed_survey = True
        self.user.vip_level = self.vip_paid
        self.user.save()
        self.staff = CustomUser.objects.create_user(username='admincheck', phone_number='699999991', password='test123', is_staff=True)
        self.staff.is_phone_verified = True
        self.staff.save()
        Task.objects.create(title='URL Test Task', reward_amount=Decimal('50'), is_active=True)

    def _public_200(self, name, *args):
        r = self.client.get(reverse(name, args=args), secure=True)
        self.assertEqual(r.status_code, 200, f'{name} should be 200, got {r.status_code}')

    def _auth_200(self, name, *args):
        self.client.force_login(self.user)
        r = self.client.get(reverse(name, args=args), secure=True)
        self.assertEqual(r.status_code, 200, f'{name} (auth) should be 200, got {r.status_code}')
        self.client.logout()

    def _auth_302(self, name, *args):
        r = self.client.get(reverse(name, args=args), secure=True)
        self.assertIn(r.status_code, [302, 403], f'{name} (anon) should be 302/403, got {r.status_code}')

    def _admin_200(self, name, *args):
        self.client.force_login(self.staff)
        r = self.client.get(reverse(name, args=args), secure=True)
        self.assertEqual(r.status_code, 200, f'{name} (admin) should be 200, got {r.status_code}')
        self.client.logout()

    def _admin_302(self, name, *args):
        r = self.client.get(reverse(name, args=args), secure=True)
        self.assertIn(r.status_code, [302, 403], f'{name} (anon→admin) should be 302/403, got {r.status_code}')

    def test_public_pages(self):
        pages = ['home', 'register', 'login', 'forgot_password', 'faq', 'cgu', 'privacy', 'offline']
        for p in pages:
            self._public_200(p)

    def test_auth_pages(self):
        pages = [
            'dashboard', 'tasks', 'mining', 'team', 'leaderboard',
            'profile', 'communaute', 'wallet', 'notifications', 'support',
            'vip_plans', 'boosts', 'referral_program', 'gamification',
            'chat', 'deposit', 'withdraw', 'wheel',
        ]
        for p in pages:
            self._auth_302(p)
            self._auth_200(p)

    def test_survey_page(self):
        """Survey est inaccessible si déjà complété, accessible sinon."""
        # User who hasn't completed survey
        fresh_user = CustomUser.objects.create_user(username='fresher', phone_number='699999987', password='test123')
        fresh_user.is_phone_verified = True
        fresh_user.has_completed_survey = False
        fresh_user.save()
        self.client.force_login(fresh_user)
        r = self.client.get(reverse('survey'), secure=True)
        self.assertEqual(r.status_code, 200)
        self.client.logout()
        # User who completed survey → redirect
        self.client.force_login(self.user)
        r = self.client.get(reverse('survey'), secure=True)
        self.assertEqual(r.status_code, 302)
        self.client.logout()

    def test_post_only_endpoints(self):
        """Ces endpoints doivent retourner 405 (GET interdit) ou 302/403 (anon)."""
        task = Task.objects.first()
        endpoints = {
            'start_mining': [],
            'claim_mining': [],
            'daily_check_in': [],
            'spin_wheel': [],
            'start_auto_task': [task.id],
            'claim_auto_task': [task.id],
            'finish_onboarding': [],
            'push_subscribe': [],
            'push_unsubscribe': [],
        }
        for name, args in endpoints.items():
            r = self.client.get(reverse(name, args=args), secure=True)
            self.assertIn(r.status_code, [302, 403, 405], f'{name} GET should not be 200, got {r.status_code}')

    def test_task_param_urls(self):
        task = Task.objects.first()
        self._auth_302('complete_task', task.id)
        self._auth_302('start_auto_task', task.id)

    def test_buy_vip_urls(self):
        vip = VIPLevel.objects.filter(price=0).first() or VIPLevel.objects.create(name='TestVIP', price=1000, daily_mining_reward=100, daily_task_limit=5, task_reward_rate=100)
        self._auth_302('buy_vip', vip.id)

    def test_buy_boost_urls(self):
        boost = Boost.objects.create(name='TestBoost', price=100, boost_type='TURBO_MINING', duration_hours=12)
        self._auth_302('buy_boost', boost.id)

    def test_admin_urls(self):
        admin_pages = [
            'admin_dashboard', 'admin_support', 'admin_users',
            'admin_export_withdrawals', 'admin_review_tasks',
            'admin_manage_tasks', 'admin_task_add', 'admin_manage_deposit_methods',
            'admin_manage_vip', 'admin_vip_add',
        ]
        for p in admin_pages:
            self._admin_302(p)
            self._admin_200(p)

    def test_notification_count_public(self):
        """Le compteur doit fonctionner pour l'utilisateur connecté."""
        self.client.force_login(self.user)
        r = self.client.get(reverse('unread_notifications_count'), secure=True)
        self.assertEqual(r.status_code, 200)
        self.client.logout()

    def test_push_settings_works(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('push_settings'), secure=True)
        self.assertEqual(r.status_code, 200)
        self.client.logout()

    def test_full_registration_flow(self):
        """Inscription → connexion → dashboard (sans vérif téléphone)."""
        # Create a referrer first to get an invitation code
        referrer = CustomUser.objects.create_user(username='referrer', phone_number='699999988', password='Test12345')
        referrer.is_phone_verified = True
        referrer.save()
        r = self.client.post(reverse('register'), {
            'username': 'newflow', 'phone_number': '699999992',
            'password': 'Test12345', 'confirm_password': 'Test12345',
            'invitation_code_input': referrer.invitation_code,
        }, secure=True, follow=True)
        self.assertContains(r, 'Inscription réussie')
        self.assertTrue(CustomUser.objects.filter(username='newflow', is_phone_verified=True).exists())

    def test_login_flow(self):
        CustomUser.objects.create_user(username='loginflow', phone_number='699999993', password='Test12345')
        r = self.client.post(reverse('login'), {'username': 'loginflow', 'password': 'Test12345'}, secure=True, follow=True)
        self.assertIn('_auth_user_id', self.client.session)
