from django.urls import path

from . import member_views, views

app_name = "ideas"

urlpatterns = [
    # Idées des membres (derrière le code d'accès)
    path("idees/", member_views.idea_list, name="list"),
    path("idees/nouvelle/", member_views.idea_new, name="new"),
    path("idees/<int:pk>/", member_views.idea_detail, name="detail"),
    path("idees/<int:pk>/modifier/", member_views.idea_edit, name="edit"),
    path("idees/<int:pk>/reagir/", member_views.idea_react, name="react"),
    path("idees/<int:pk>/statut/", member_views.idea_status, name="status"),
    # Propositions extérieures
    path("p/proposer/", views.propose, name="propose"),
    path("p/proposer/envoyee/", views.sent, name="sent"),
    path("p/suivi/<uuid:token>/", views.track, name="track"),
    path("gestion/moderation/", views.moderation, name="moderation"),
    path("gestion/moderation/<int:pk>/accepter/", views.moderation_accept, name="accept"),
    path("gestion/moderation/<int:pk>/refuser/", views.moderation_refuse, name="refuse"),
    path("gestion/moderation/ecarter/", views.moderation_refuse_bulk, name="refuse_bulk"),
]
