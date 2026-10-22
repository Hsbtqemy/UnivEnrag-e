from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("p/", views.home, name="home"),
    path("p/actualites/", views.news_list, name="news_list"),
    path("p/actualites.rss", views.news_feed, name="news_feed"),
    path("p/actualites/<slug:slug>/", views.news_detail, name="news_detail"),
    path("p/contact/", views.contact, name="contact"),
    path("gestion/presentation/", views.presentation, name="presentation"),
]
