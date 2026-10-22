from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "agenda"

urlpatterns = [
    path("agenda/", views.public_list, name="public_list"),
    path("agenda/semaine/", views.public_week, name="public_week"),
    path("agenda/evenements.json", views.public_events_json, name="public_events_json"),
    path("agenda/<int:pk>/", views.public_detail, name="public_detail"),
    path("agenda.ics", views.public_ics, name="public_ics"),
    path("gestion/", RedirectView.as_view(pattern_name="agenda:programming"), name="gestion"),
    path("gestion/programmation/", views.programming, name="programming"),
    path("gestion/api/evenements/", views.gestion_events, name="gestion_events"),
    path("gestion/api/evenements/<int:pk>/deplacer/", views.gestion_move, name="gestion_move"),
    path("gestion/api/evenements/<int:pk>/public/", views.gestion_public, name="gestion_public"),
    path("gestion/api/evenements/confirmer/", views.gestion_confirm, name="gestion_confirm"),
    path("gestion/api/propositions/<int:pk>/placer/", views.gestion_place, name="gestion_place"),
]
