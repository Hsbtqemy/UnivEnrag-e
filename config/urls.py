from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import admin_login

admin.site.site_header = "Université Enragée — administration"
admin.site.site_title = "Administration"
admin.site.site_url = "/accueil/"

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.actors.urls")),
    path("", include("apps.ideas.urls")),
    path("", include("apps.agenda.urls")),
    path("", include("apps.presences.urls")),
    path("", include("apps.polls.urls")),
    path("", include("apps.public.urls")),
    # Avant l'admin : sa page de connexion, avec une limite d'échecs.
    path("gestion/admin/login/", admin_login, name="admin_login"),
    path("gestion/admin/", admin.site.urls),
]
