from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.root, name="root"),
    path("acces/", views.access_code, name="access"),
    path("robots.txt", views.robots_txt, name="robots"),
]
