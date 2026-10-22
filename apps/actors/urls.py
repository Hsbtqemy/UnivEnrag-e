from django.urls import path

from . import views

app_name = "actors"

urlpatterns = [
    path("nom/", views.name, name="name"),
]
