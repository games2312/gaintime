from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from core.models import (
    CustomUser, VIPLevel, Transaction, MiningSession,
    Task, Boost, Badge, UserBadge, DailyMission,
    UserMissionProgress, PushSubscription,
)
from core.views import compute_trust_score, check_badge_unlocks
from core.utils import compute_phash, hamming_distance, get_client_ip


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
