import copy
import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from wger.manager.models import Routine


CONFIG_RELATIONS = [
    'weightconfig', 'maxweightconfig',
    'repetitionsconfig', 'maxrepetitionsconfig',
    'setsconfig', 'maxsetsconfig',
    'restconfig', 'maxrestconfig',
    'rirconfig', 'maxrirconfig',
]


def _check_trainer(request):
    if not request.user.has_perm('gym.gym_trainer'):
        return None, HttpResponseForbidden()
    gym = request.user.userprofile.gym
    if not gym:
        return None, HttpResponseForbidden()
    return gym, None


@login_required
def assign_routine(request, routine_pk):
    """Select client -> assign routine to them"""
    gym, err = _check_trainer(request)
    if err:
        return err

    routine = get_object_or_404(Routine, pk=routine_pk)
    clients = User.objects.filter(
        userprofile__gym=gym
    ).exclude(pk=request.user.pk).order_by('username')

    error = None
    success = None

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        if not client_id:
            error = 'Выберите клиента'
        else:
            client = get_object_or_404(User, pk=client_id)
            if client.userprofile.gym_id != gym.pk:
                return HttpResponseForbidden()
            _copy_routine_to_user(routine, client)
            success = client
            try:
                from wger.core.views.push import send_push
                send_push(client, "Новая программа", f"Тренер назначил программу {routine.name}", "/routine/overview")
            except Exception:
                pass

    return render(request, 'assign_routine.html', {
        'routine': routine,
        'clients': clients,
        'error': error,
        'success': success,
        'mode': 'select_client',
    })


@login_required
def assign_to_client(request, client_pk):
    """Select routine -> assign to this client"""
    gym, err = _check_trainer(request)
    if err:
        return err

    client = get_object_or_404(User, pk=client_pk)
    if client.userprofile.gym_id != gym.pk:
        return HttpResponseForbidden()

    routines = Routine.objects.filter(user=request.user).order_by('-created')

    error = None
    success = None

    if request.method == 'POST':
        routine_id = request.POST.get('routine_id')
        if not routine_id:
            error = 'Выберите программу'
        else:
            routine = get_object_or_404(Routine, pk=routine_id, user=request.user)
            _copy_routine_to_user(routine, client)
            success = routine
            try:
                from wger.core.views.push import send_push
                send_push(client, "Новая программа", f"Тренер назначил программу {routine.name}", "/routine/overview")
            except Exception:
                pass

    return render(request, 'assign_to_client.html', {
        'client': client,
        'routines': routines,
        'error': error,
        'success': success,
    })


def _copy_routine_to_user(routine, target_user):
    if routine.start and routine.end:
        duration = routine.end - routine.start
    else:
        duration = datetime.timedelta(days=90)

    r = copy.copy(routine)
    r.pk = None
    r.created = None
    r.user = target_user
    r.is_template = False
    r.is_public = False
    r.start = datetime.date.today()
    r.end = r.start + duration
    r.save()

    for day in routine.days.all():
        d = copy.copy(day)
        d.pk = None
        d.routine = r
        d.save()

        for slot in day.slots.all():
            s = copy.copy(slot)
            s.pk = None
            s.day = d
            s.save()

            for entry in slot.entries.all():
                e = copy.copy(entry)
                e.pk = None
                e.slot = s
                e.save()

                for rel in CONFIG_RELATIONS:
                    manager = getattr(entry, rel, None)
                    if manager is None:
                        continue
                    for config in manager.all():
                        c = copy.copy(config)
                        c.pk = None
                        c.slot_entry = e
                        c.save()

    return r
