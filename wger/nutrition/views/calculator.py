import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from wger.nutrition.forms import (
    BmrForm,
    DailyCaloriesForm,
    PhysicalActivitiesForm,
)

logger = logging.getLogger(__name__)


def view(request):
    form_data = {}
    if request.user.is_authenticated:
        form_data = {
            'age': request.user.userprofile.age,
            'height': request.user.userprofile.height,
            'gender': request.user.userprofile.gender,
            'weight': request.user.userprofile.weight,
        }

    context = {
        'form': BmrForm(initial=form_data),
        'form_activities': PhysicalActivitiesForm(
            instance=request.user.userprofile if request.user.is_authenticated else None
        ),
        'form_calories': DailyCaloriesForm(
            instance=request.user.userprofile if request.user.is_authenticated else None
        ),
    }
    return render(request, 'rate/form.html', context)


@login_required
def calculate_bmr(request):
    data = {}
    form = BmrForm(data=request.POST, instance=request.user.userprofile)
    if form.is_valid():
        form.save()
        request.user.userprofile.user_bodyweight(form.cleaned_data['weight'])
        bmr = request.user.userprofile.calculate_basal_metabolic_rate()
        result = {'bmr': '{0:.0f}'.format(bmr)}
        data = json.dumps(result)
    else:
        logger.debug(form.errors)
        data = json.dumps({'bmr': str(form.errors)})
    return HttpResponse(data, 'application/json')


@login_required
def calculate_activities(request):
    data = {}
    form = PhysicalActivitiesForm(data=request.POST, instance=request.user.userprofile)
    if form.is_valid():
        form.save()
        factor = request.user.userprofile.calculate_activities()
        total = request.user.userprofile.calculate_basal_metabolic_rate() * factor
        result = {'activities': '{0:.0f}'.format(total), 'factor': '{0:.2f}'.format(factor)}
        data = json.dumps(result)
    else:
        logger.debug(form.errors)
        data = json.dumps({'activities': str(form.errors)})
    return HttpResponse(data, 'application/json')
