"""Tests for REP12 custom views: assign, push, call."""

import datetime
import hashlib
import json
from unittest.mock import patch, MagicMock

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


class CallLinkApiTest(WgerTestCase):
    """Tests for call_link API endpoint."""

    def test_anon_redirects(self):
        resp = self.client.get('/api/call/link/')
        self.assertEqual(resp.status_code, 302)

    def test_user_with_gym_gets_link(self):
        self.user_login('admin')  # admin has gym=1
        resp = self.client.get('/api/call/link/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('room_code', data)
        self.assertIn('call_url', data)
        self.assertEqual(len(data['room_code']), 5)
        self.assertTrue(data['room_code'].isdigit())

    def test_user_without_gym_404(self):
        self.user_login('test')  # test has gym via fixture, check
        from django.contrib.auth.models import User
        u = User.objects.get(username='test')
        u.userprofile.gym = None
        u.userprofile.save()
        resp = self.client.get('/api/call/link/')
        self.assertEqual(resp.status_code, 404)

    def test_same_gym_same_code(self):
        """Users in same gym get same room code."""
        self.user_login('trainer1')  # gym=1
        resp1 = self.client.get('/api/call/link/')
        code1 = resp1.json()['room_code']
        self.user_logout()

        self.user_login('trainer2')  # gym=1
        resp2 = self.client.get('/api/call/link/')
        code2 = resp2.json()['room_code']
        self.assertEqual(code1, code2)

    def test_code_matches_gym_id(self):
        """API room code matches _get_room_code for user's gym."""
        from wger.core.views.call import _get_room_code

        self.user_login('trainer1')  # gym=1
        resp = self.client.get('/api/call/link/')
        code = resp.json()['room_code']
        expected = _get_room_code(1)
        self.assertEqual(code, expected)


class CopyRoutineWithConfigsTest(WgerTestCase):
    """Tests that _copy_routine_to_user copies all nested objects."""

    def test_copy_preserves_structure(self):
        """Copied routine has same day/slot/entry structure."""
        from wger.core.views.assign import _copy_routine_to_user
        from wger.manager.models import Routine

        self.user_login('trainer1')
        src = _make_routine(4, 'Structure test')

        # Add a day with a slot and entry
        from wger.manager.models import Day, Slot, SlotEntry
        day = Day.objects.create(routine=src, name='Day A', order=1)
        slot = Slot.objects.create(day=day, order=1)
        from wger.exercises.models import Exercise
        ex = Exercise.objects.first()
        if ex:
            entry = SlotEntry.objects.create(slot=slot, exercise=ex, order=1)

        from django.contrib.auth.models import User
        target = User.objects.get(pk=2)
        copied = _copy_routine_to_user(src, target)

        self.assertEqual(copied.user, target)
        self.assertEqual(copied.name, 'Structure test')
        self.assertFalse(copied.is_template)
        self.assertFalse(copied.is_public)
        self.assertEqual(copied.days.count(), src.days.count())

        if ex:
            copied_day = copied.days.first()
            self.assertEqual(copied_day.slots.count(), 1)
            copied_slot = copied_day.slots.first()
            self.assertEqual(copied_slot.entries.count(), 1)

        copied.delete()
        src.delete()

    def test_copy_sets_correct_dates(self):
        """Copied routine starts today and preserves duration."""
        from wger.core.views.assign import _copy_routine_to_user
        from django.contrib.auth.models import User

        src = _make_routine(4, 'Date test')
        src.start = datetime.date.today() - datetime.timedelta(days=30)
        src.end = datetime.date.today() + datetime.timedelta(days=60)
        src.save()

        target = User.objects.get(pk=2)
        copied = _copy_routine_to_user(src, target)

        self.assertEqual(copied.start, datetime.date.today())
        duration = src.end - src.start
        self.assertEqual(copied.end, datetime.date.today() + duration)

        copied.delete()
        src.delete()

    def test_copy_does_not_mutate_source(self):
        """Source routine is unchanged after copy."""
        from wger.core.views.assign import _copy_routine_to_user
        from wger.manager.models import Routine
        from django.contrib.auth.models import User

        src = _make_routine(4, 'Immutable test')
        src_pk = src.pk
        src_name = src.name
        src_user = src.user_id

        target = User.objects.get(pk=2)
        _copy_routine_to_user(src, target)

        src.refresh_from_db()
        self.assertEqual(src.pk, src_pk)
        self.assertEqual(src.name, src_name)
        self.assertEqual(src.user_id, src_user)

        Routine.objects.filter(user=target, name='Immutable test').delete()
        src.delete()


class SendPushTest(WgerTestCase):
    """Tests for send_push function."""

    def test_no_vapid_key_returns_silently(self):
        """Without VAPID key, send_push does nothing."""
        from wger.core.views.push import send_push
        from django.contrib.auth.models import User
        user = User.objects.get(pk=2)

        with patch.dict('os.environ', {}, clear=False):
            if 'VAPID_PRIVATE_KEY' in __import__('os').environ:
                del __import__('os').environ['VAPID_PRIVATE_KEY']
            # Should not raise
            send_push(user, 'Test', 'Body')

    @patch('pywebpush.webpush')
    def test_push_called_for_each_subscription(self, mock_webpush):
        """send_push calls webpush for each user subscription."""
        from wger.core.views.push import send_push
        from wger.gym.models import PushSubscription
        from django.contrib.auth.models import User

        user = User.objects.get(pk=2)
        PushSubscription.objects.create(
            user=user, endpoint='https://fcm.test/a', p256dh='k1', auth='a1'
        )
        PushSubscription.objects.create(
            user=user, endpoint='https://fcm.test/b', p256dh='k2', auth='a2'
        )

        with patch.dict('os.environ', {'VAPID_PRIVATE_KEY': 'test-key'}):
            send_push(user, 'Hello', 'World', '/test')

        self.assertEqual(mock_webpush.call_count, 2)
        PushSubscription.objects.filter(user=user).delete()

    @patch('pywebpush.webpush')
    def test_push_removes_gone_subscription(self, mock_webpush):
        """410 Gone subscriptions are cleaned up."""
        from wger.core.views.push import send_push
        from wger.gym.models import PushSubscription
        from django.contrib.auth.models import User

        user = User.objects.get(pk=2)
        sub = PushSubscription.objects.create(
            user=user, endpoint='https://fcm.test/gone', p256dh='k', auth='a'
        )

        mock_webpush.side_effect = Exception('410 Gone')
        with patch.dict('os.environ', {'VAPID_PRIVATE_KEY': 'test-key'}):
            send_push(user, 'Test', 'Body')

        self.assertFalse(
            PushSubscription.objects.filter(pk=sub.pk).exists()
        )


class AssignRoutineIntegrationTest(WgerTestCase):
    """Full integration tests for the assign workflow."""

    def test_assign_routine_full_flow(self):
        """Trainer creates routine, assigns to client, client has it."""
        from wger.manager.models import Routine

        self.user_login('trainer1')
        src = _make_routine(4, 'Full flow')

        # POST to assign
        resp = self.client.post(
            f'/routine/{src.pk}/assign/',
            {'client_id': 2},
        )
        self.assertEqual(resp.status_code, 200)

        # Client now has the routine
        client_routines = Routine.objects.filter(user_id=2, name='Full flow')
        self.assertEqual(client_routines.count(), 1)
        copied = client_routines.first()
        self.assertEqual(copied.start, datetime.date.today())
        self.assertFalse(copied.is_template)

        client_routines.delete()
        src.delete()

    def test_assign_to_client_full_flow(self):
        """Trainer picks routine from own list, assigns to specific client."""
        from wger.manager.models import Routine

        self.user_login('trainer1')
        src = _make_routine(4, 'Pick and assign')

        resp = self.client.post(
            '/user/2/assign-routine/',
            {'routine_id': src.pk},
        )
        self.assertEqual(resp.status_code, 200)

        client_routines = Routine.objects.filter(user_id=2, name='Pick and assign')
        self.assertTrue(client_routines.exists())
        client_routines.delete()
        src.delete()

    def test_assign_sends_push_notification(self):
        """Assigning routine triggers push notification."""
        self.user_login('trainer1')
        src = _make_routine(4, 'Push test')

        with patch('wger.core.views.push.send_push') as mock_push:
            self.client.post(
                f'/routine/{src.pk}/assign/',
                {'client_id': 2},
            )
            mock_push.assert_called_once()
            args = mock_push.call_args[0]
            self.assertEqual(args[0].pk, 2)  # client user
            self.assertIn('Push test', args[2])  # routine name in body

        from wger.manager.models import Routine
        Routine.objects.filter(user_id=2, name='Push test').delete()
        src.delete()

    def test_double_assign_creates_two_copies(self):
        """Assigning same routine twice creates two separate copies."""
        from wger.manager.models import Routine

        self.user_login('trainer1')
        src = _make_routine(4, 'Double')

        self.client.post(f'/routine/{src.pk}/assign/', {'client_id': 2})
        self.client.post(f'/routine/{src.pk}/assign/', {'client_id': 2})

        copies = Routine.objects.filter(user_id=2, name='Double')
        self.assertEqual(copies.count(), 2)
        copies.delete()
        src.delete()


class PushSubscriptionEdgeCasesTest(WgerTestCase):
    """Edge case tests for push subscribe/unsubscribe."""

    def test_subscribe_duplicate_updates(self):
        """Subscribing same endpoint twice updates instead of creating duplicate."""
        from wger.gym.models import PushSubscription

        self.user_login('test')
        payload = json.dumps({
            'endpoint': 'https://fcm.test/dup',
            'keys': {'p256dh': 'key1', 'auth': 'auth1'},
        })
        self.client.post('/api/v2/push/subscribe/', data=payload, content_type='application/json')
        self.client.post(
            '/api/v2/push/subscribe/',
            data=json.dumps({
                'endpoint': 'https://fcm.test/dup',
                'keys': {'p256dh': 'key2', 'auth': 'auth2'},
            }),
            content_type='application/json',
        )

        subs = PushSubscription.objects.filter(user_id=2, endpoint='https://fcm.test/dup')
        self.assertEqual(subs.count(), 1)
        self.assertEqual(subs.first().p256dh, 'key2')
        subs.delete()

    def test_unsubscribe_nonexistent_ok(self):
        """Unsubscribing non-existent endpoint returns 200."""
        self.user_login('test')
        resp = self.client.post(
            '/api/v2/push/unsubscribe/',
            data=json.dumps({'endpoint': 'https://fcm.test/noexist'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_subscribe_empty_body(self):
        """Empty body returns 400 or 500."""
        self.user_login('test')
        resp = self.client.post(
            '/api/v2/push/subscribe/',
            data='',
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 500])

    def test_user_cannot_see_other_subscriptions(self):
        """User's unsubscribe only affects own subscriptions."""
        from wger.gym.models import PushSubscription

        PushSubscription.objects.create(
            user_id=1, endpoint='https://fcm.test/admin', p256dh='k', auth='a'
        )

        self.user_login('test')
        self.client.post(
            '/api/v2/push/unsubscribe/',
            data=json.dumps({'endpoint': 'https://fcm.test/admin'}),
            content_type='application/json',
        )

        # Admin's subscription should still exist
        self.assertTrue(
            PushSubscription.objects.filter(user_id=1, endpoint='https://fcm.test/admin').exists()
        )
        PushSubscription.objects.filter(endpoint='https://fcm.test/admin').delete()
