from django.urls import path

from . import feeds, member_views, views

app_name = "agenda"

urlpatterns = [
    path("accueil/", views.home, name="home"),
    # Agenda des membres (derrière le code d'accès)
    path("agenda/", member_views.calendar, name="calendar"),
    path("agenda/evenements.json", member_views.events_json, name="events_json"),
    path("agenda/verifier/", member_views.check_slot, name="check"),
    path("agenda/nouveau/", member_views.new, name="new"),
    path("agenda/<int:pk>/", member_views.detail, name="detail"),
    path("agenda/<int:pk>/modifier/", member_views.edit, name="edit"),
    path("agenda/<int:pk>/annuler/", member_views.cancel, name="cancel"),
    path("agenda/<int:pk>/verrou/", member_views.toggle_lock, name="lock"),
    path("agenda/<int:pk>/confirmer/", member_views.confirm, name="confirm"),
    path("agenda/<int:pk>/publier/", member_views.publish, name="publish"),
    path("agenda/<int:pk>/restaurer/<int:change_id>/", member_views.restore, name="restore"),
    path("agenda/api/evenements/<int:pk>/deplacer/", member_views.move, name="move"),
    path("gestion/publication/", member_views.public_requests, name="public_requests"),
    path("gestion/salles/", member_views.room_requests, name="room_requests"),
    path("salles/", member_views.rooms, name="rooms"),
    path("agenda/abonnements/", feeds.subscriptions, name="subscriptions"),
    path("flux/<str:token>/agenda.ics", feeds.feed_all, name="feed_all"),
    path("flux/<str:token>/espace/<slug:slug>.ics", feeds.feed_space, name="feed_space"),
    path("flux/<str:token>/salle/<int:pk>.ics", feeds.feed_room, name="feed_room"),
    # Agenda public
    path("p/agenda/", views.public_list, name="public_list"),
    path("p/agenda/semaine/", views.public_week, name="public_week"),
    path("p/agenda/evenements.json", views.public_events_json, name="public_events_json"),
    path("p/agenda/<int:pk>/", views.public_detail, name="public_detail"),
    path("p/agenda.ics", views.public_ics, name="public_ics"),
    # Programmation : placer et déplacer pour tous, confirmer et publier pour les habilités
    path("agenda/programmation/", views.programming, name="programming"),
    path(
        "agenda/programmation/evenements.json",
        views.programming_events,
        name="programming_events",
    ),
    path("agenda/api/idees/<int:pk>/placer/", views.place_idea, name="place_idea"),
    path("gestion/api/evenements/<int:pk>/public/", views.gestion_public, name="gestion_public"),
    path("gestion/api/evenements/confirmer/", views.gestion_confirm, name="gestion_confirm"),
]
