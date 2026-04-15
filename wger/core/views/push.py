import json
import logging
import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@login_required
@require_POST
def subscribe(request):
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
            return JsonResponse({'error': 'Invalid subscription'}, status=400)

        from wger.gym.models import PushSubscription
        PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=endpoint,
            defaults={
                'p256dh': keys['p256dh'],
                'auth': keys['auth'],
            }
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        logger.exception('Push subscribe error')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def unsubscribe(request):
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        from wger.gym.models import PushSubscription
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def send_push(user, title, body, url='/dashboard'):
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning('pywebpush not installed, skipping push')
        return

    vapid_private = os.environ.get('VAPID_PRIVATE_KEY')
    vapid_email = os.environ.get('VAPID_CLAIM_EMAIL', 'mailto:info@rep12.ru')
    if not vapid_private:
        logger.warning('VAPID_PRIVATE_KEY not configured')
        return

    from wger.gym.models import PushSubscription
    subs = PushSubscription.objects.filter(user=user)
    payload = json.dumps({'title': title, 'body': body, 'url': url})

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={'sub': vapid_email},
            )
        except Exception as e:
            logger.warning(f'Push failed for {sub.endpoint[:50]}: {e}')
            if 'gone' in str(e).lower() or '410' in str(e):
                sub.delete()
