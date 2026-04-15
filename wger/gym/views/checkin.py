import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.models import User

from wger.gym.models.checkin import CheckIn


@login_required
def checkin_create(request):
    today = datetime.date.today()
    existing = CheckIn.objects.filter(user=request.user, date=today).first()

    if request.method == 'POST':
        mood = request.POST.get('mood')
        energy = request.POST.get('energy')
        sleep = request.POST.get('sleep')
        notes = request.POST.get('notes', '')

        if not all([mood, energy, sleep]):
            return render(request, 'gym/checkin_form.html', {
                'error': 'Заполните все поля',
                'existing': existing,
                'mood_choices': CheckIn.MOOD_CHOICES,
                'range_5': range(1, 6),
            })

        if existing:
            existing.mood = int(mood)
            existing.energy = int(energy)
            existing.sleep = int(sleep)
            existing.notes = notes
            existing.save()
        else:
            CheckIn.objects.create(
                user=request.user,
                mood=int(mood),
                energy=int(energy),
                sleep=int(sleep),
                notes=notes,
            )

        return redirect('gym:checkin:history')

    return render(request, 'gym/checkin_form.html', {
        'existing': existing,
        'mood_choices': CheckIn.MOOD_CHOICES,
        'range_5': range(1, 6),
    })


@login_required
def checkin_history(request):
    checkins = CheckIn.objects.filter(user=request.user)[:30]
    return render(request, 'gym/checkin_history.html', {
        'checkins': checkins,
    })


@login_required
def checkin_client(request, client_pk):
    if not request.user.has_perm('gym.gym_trainer'):
        return HttpResponseForbidden()
    gym = request.user.userprofile.gym
    if not gym:
        return HttpResponseForbidden()

    client = get_object_or_404(User, pk=client_pk)
    if client.userprofile.gym_id != gym.pk:
        return HttpResponseForbidden()

    checkins = CheckIn.objects.filter(user=client)[:30]
    return render(request, 'gym/checkin_client.html', {
        'client': client,
        'checkins': checkins,
    })
