"""Tests for REP12 custom views: assign, push, call."""

import datetime
import hashlib
import json

from django.test import TestCase
from django.urls import reverse

from wger.core.tests.base_testcase import WgerTestCase


def _make_routine(user_id, name='Test routine'):
    """Helper to create a routine with required fields."""
    from wger.manager.models import Routine

    today = datetime.date.today()
    return Routine.objects.create(
        user_id=user_id,
        name=name,
        start=today,
        end=today + datetime.timedelta(days=90),
    )


class AssignRoutineTest(WgerTestCase):
    """Tests for assign_routine view."""

    def test_anon_redirects(self):
        """Anonymous user should be redirected to login."""
        resp = self.client.get('/routine/1/assign/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_non_trainer_forbidden(self):
        """Regular user (no gym_trainer perm) gets 403."""
        self.user_login('test')
        resp = self.client.get('/routine/1/assign/')
        self.assertEqual(resp.status_code, 403)

    def test_trainer_can_access(self):
        """Trainer can access assign page for own routine."""
        self.user_login('trainer1')
        # trainer1 pk=4, needs a routine owned by trainer1
        r = _make_routine(4, 'Test assign')
        resp = self.client.get(f'/routine/{r.pk}/assign/')
        self.assertEqual(resp.status_code, 200)
        r.delete()

    def test_trainer_cannot_access_others_routine(self):
        """Trainer cannot assign a routine they don't own."""
        self.user_login('trainer1')
        # routine pk=1 belongs to admin (user=1)
        resp = self.client.get('/routine/1/assign/')
        self.assertEqual(resp.status_code, 404)

    def test_assign_copies_routine(self):
        """POST to assign_routine copies routine to client."""
        self.user_login('trainer1')
        src = _make_routine(4, 'Copy test')
        # test user pk=2 is in same gym (gym=1)
        resp = self.client.post(
            f'/routine/{src.pk}/assign/',
            {'client_id': 2},
        )
        self.assertEqual(resp.status_code, 200)
        from wger.manager.models import Routine
        copied = Routine.objects.filter(user_id=2, name='Copy test')
        self.assertTrue(copied.exists())
        copied.delete()
        src.delete()

    def test_assign_cross_gym_forbidden(self):
        """Trainer cannot assign to user in different gym."""
        self.user_login('trainer1')
        src = _make_routine(4, 'Cross gym')
        # demo user pk=3 is in gym=2, trainer1 is in gym=1
        resp = self.client.post(
            f'/routine/{src.pk}/assign/',
            {'client_id': 3},
        )
        self.assertEqual(resp.status_code, 403)
        src.delete()


class AssignToClientTest(WgerTestCase):
    """Tests for assign_to_client view."""

    def test_anon_redirects(self):
        resp = self.client.get('/user/2/assign-routine/')
        self.assertEqual(resp.status_code, 302)

    def test_non_trainer_forbidden(self):
        self.user_login('test')
        resp = self.client.get('/user/2/assign-routine/')
        self.assertEqual(resp.status_code, 403)

    def test_trainer_can_access_same_gym_client(self):
        self.user_login('trainer1')
        resp = self.client.get('/user/2/assign-routine/')
        self.assertEqual(resp.status_code, 200)

    def test_trainer_cannot_access_other_gym_client(self):
        self.user_login('trainer1')
        # demo pk=3, gym=2
        resp = self.client.get('/user/3/assign-routine/')
        self.assertEqual(resp.status_code, 403)


class PushSubscribeTest(WgerTestCase):
    """Tests for push subscribe/unsubscribe endpoints."""

    def test_anon_subscribe_redirects(self):
        resp = self.client.post(
            '/api/v2/push/subscribe/',
            data=json.dumps({'endpoint': 'https://fcm.test/123', 'keys': {'p256dh': 'a', 'auth': 'b'}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        self.user_login('test')
        resp = self.client.get('/api/v2/push/subscribe/')
        self.assertEqual(resp.status_code, 405)

    def test_subscribe_missing_fields(self):
        self.user_login('test')
        resp = self.client.post(
            '/api/v2/push/subscribe/',
            data=json.dumps({'endpoint': 'https://fcm.test/123'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_subscribe_success(self):
        self.user_login('test')
        resp = self.client.post(
            '/api/v2/push/subscribe/',
            data=json.dumps({
                'endpoint': 'https://fcm.test/unique123',
                'keys': {'p256dh': 'testkey', 'auth': 'testauth'},
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))

        from wger.gym.models import PushSubscription

        sub = PushSubscription.objects.filter(user_id=2, endpoint='https://fcm.test/unique123')
        self.assertTrue(sub.exists())
        sub.delete()

    def test_unsubscribe_success(self):
        self.user_login('test')
        from wger.gym.models import PushSubscription

        PushSubscription.objects.create(
            user_id=2, endpoint='https://fcm.test/del456', p256dh='k', auth='a'
        )
        resp = self.client.post(
            '/api/v2/push/unsubscribe/',
            data=json.dumps({'endpoint': 'https://fcm.test/del456'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            PushSubscription.objects.filter(endpoint='https://fcm.test/del456').exists()
        )


class CallRoomCodeTest(TestCase):
    """Tests for _get_room_code determinism and safety."""

    def test_room_code_deterministic(self):
        from wger.core.views.call import _get_room_code

        code1 = _get_room_code(1)
        code2 = _get_room_code(1)
        self.assertEqual(code1, code2)

    def test_room_code_different_gyms(self):
        from wger.core.views.call import _get_room_code

        code1 = _get_room_code(1)
        code2 = _get_room_code(2)
        self.assertNotEqual(code1, code2)

    def test_room_code_5_digits(self):
        from wger.core.views.call import _get_room_code

        code = _get_room_code(42)
        self.assertEqual(len(code), 5)
        self.assertTrue(code.isdigit())
        self.assertGreaterEqual(int(code), 10000)
        self.assertLessEqual(int(code), 99999)

    def test_no_global_state(self):
        """Ensure room code doesn't pollute global random."""
        import random

        random.seed(999)
        val_before = random.random()
        random.seed(999)

        from wger.core.views.call import _get_room_code

        _get_room_code(1)
        val_after = random.random()
        self.assertEqual(val_before, val_after)


class CallRoomViewTest(WgerTestCase):
    """Tests for call_room view."""

    def test_anon_redirects(self):
        resp = self.client.get('/call/12345')
        self.assertEqual(resp.status_code, 302)

    def test_wrong_code_404(self):
        self.user_login('test')
        resp = self.client.get('/call/00000')
        self.assertEqual(resp.status_code, 404)
