import logging

from django.conf import settings
from django.shortcuts import render
from django.urls import reverse

from wger.core.forms import (
    RegistrationForm,
    RegistrationFormNoCaptcha,
)

logger = logging.getLogger(__name__)


def features(request):
    FormClass = (
        RegistrationForm if settings.WGER_SETTINGS['USE_RECAPTCHA'] else RegistrationFormNoCaptcha
    )
    form = FormClass()
    form.fields['username'].widget.attrs.pop('autofocus', None)
    form.helper.form_action = reverse('core:user:registration')

    context = {
        'form': form,
        'allow_registration': settings.WGER_SETTINGS['ALLOW_REGISTRATION'],
        'allow_guest_users': settings.WGER_SETTINGS['ALLOW_GUEST_USERS'],
    }
    return render(request, 'features.html', context)
