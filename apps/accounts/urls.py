from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("gestion/", views.gestion_home, name="gestion_home"),
    path("gestion/2fa/configurer/", views.setup, name="2fa_setup"),
    path("gestion/2fa/configurer/qr.svg", views.setup_qr, name="2fa_qr"),
    path("gestion/2fa/verifier/", views.verify, name="2fa_verify"),
    path("gestion/sauvegarde/", views.backup_download, name="backup"),
]
