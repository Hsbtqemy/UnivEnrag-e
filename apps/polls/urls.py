from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("sondages/", views.poll_list, name="list"),
    path("sondages/nouveau/", views.poll_new, name="new"),
    path("sondages/<int:pk>/", views.poll_detail, name="detail"),
]
