import hashlib
import os
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from livekit.api import AccessToken, VideoGrants

LIVEKIT_API_KEY = os.environ.get('LIVEKIT_API_KEY', 'rep12api')
LIVEKIT_API_SECRET = os.environ.get('LIVEKIT_API_SECRET', '')
LIVEKIT_URL = os.environ.get('LIVEKIT_URL', 'ws://localhost:7880')


def _get_room_code(gym_id):
    """Generate a stable 5-digit room code from gym_id"""
    h = hashlib.sha256(f'rep12_room_{gym_id}'.encode()).hexdigest()
    code = int(h[:8], 16) % 90000 + 10000
    return str(code)


@login_required
def call_room(request, room_code):
    """Video call room page"""
    profile = request.user.userprofile
    gym = profile.gym

    if not gym:
        raise Http404('No gym assigned')

    expected_code = _get_room_code(gym.pk)
    if room_code != expected_code:
        raise Http404('Invalid room code')

    # Generate LiveKit token
    room_name = f'rep12_{room_code}'
    display_name = request.user.get_full_name() or request.user.username

    token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.identity = request.user.username
    token.name = display_name
    grant = VideoGrants(
        room_join=True,
        room=room_name,
    )
    token.video_grants = grant
    jwt_token = token.to_jwt()

    # Determine if user is trainer
    is_trainer = request.user.has_perm('gym.gym_trainer')

    context = {
        'room_code': room_code,
        'room_name': room_name,
        'livekit_url': LIVEKIT_URL,
        'livekit_token': jwt_token,
        'display_name': display_name,
        'is_trainer': is_trainer,
        'gym_name': gym.name,
    }
    return render(request, 'call_room.html', context)


@login_required
def call_link(request):
    """Get call link for current user's gym"""
    profile = request.user.userprofile
    gym = profile.gym

    if not gym:
        return JsonResponse({'error': 'No gym'}, status=404)

    room_code = _get_room_code(gym.pk)
    call_url = request.build_absolute_uri(f'/call/{room_code}')

    return JsonResponse({
        'room_code': room_code,
        'call_url': call_url,
    })
