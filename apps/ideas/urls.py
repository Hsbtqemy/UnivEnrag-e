from django.urls import path

from . import views

app_name = "ideas"

urlpatterns = [
    path("proposer/", views.propose, name="propose"),
    path("proposer/envoyee/", views.sent, name="sent"),
    path("suivi/<uuid:token>/", views.track, name="track"),
    path("gestion/moderation/", views.moderation, name="moderation"),
    path("gestion/moderation/<int:pk>/accepter/", views.moderation_accept, name="accept"),
    path("gestion/moderation/<int:pk>/refuser/", views.moderation_refuse, name="refuse"),
    path("gestion/moderation/ecarter/", views.moderation_refuse_bulk, name="refuse_bulk"),
]
