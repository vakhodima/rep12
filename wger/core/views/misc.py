# Patched misc.py view - index renders features page directly for non-authenticated users
# This file replaces just the index function behavior

# Original import path
from wger.core.views.misc import *  # noqa: keep all original exports

# Override the index function  
def _patched_index(request):
    """Index page - render features directly for anonymous users"""
    from django.http import HttpResponseRedirect
    from django.urls import reverse
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse("core:dashboard"))
    else:
        from wger.software.views import features
        return features(request)
