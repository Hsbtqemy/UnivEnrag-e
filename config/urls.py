from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Plateforme du collectif — administration"
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
    path("gestion/admin/", admin.site.urls),
]
