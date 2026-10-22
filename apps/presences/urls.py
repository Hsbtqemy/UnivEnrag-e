from django.urls import path

from . import views

app_name = "presences"

urlpatterns = [
    path("presences/", views.board, name="board"),
    path("presences/ma-semaine/", views.my_week, name="my_week"),
]
