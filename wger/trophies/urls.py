from django.urls import path
from wger.core.views.react import ReactView
from wger.trophies.views import TrophiesOverview
from wger.trophies import views_custom

urlpatterns = [
    path(
        '',
        views_custom.my_trophies,
        name='overview',
    ),
    path(
        'admin',
        TrophiesOverview.as_view(),
        name='admin-overview',
    ),
]
