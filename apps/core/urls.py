from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.root, name="root"),
    path("acces/", views.access_code, name="access"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("sante/", views.health, name="health"),
    path("aide/", views.help_page, name="help"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("hors-ligne/", views.offline, name="offline"),
    path("p/donnees-personnelles/", views.privacy, name="privacy"),
]
