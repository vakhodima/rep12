import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from wger.trophies.models import Trophy, UserTrophy

logger = logging.getLogger(__name__)


@login_required
def my_trophies(request):
    user_trophies = UserTrophy.objects.filter(
        user=request.user
    ).select_related('trophy').order_by('-earned_at')

    earned_ids = set(ut.trophy_id for ut in user_trophies)
    locked_trophies = Trophy.objects.filter(
        is_active=True
    ).exclude(id__in=earned_ids).order_by('order', 'pk')

    return render(request, 'trophies/overview.html', {
        'user_trophies': user_trophies,
        'locked_trophies': locked_trophies,
    })
