from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "Plateforme du collectif — administration"
admin.site.site_title = "Administration"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="agenda:public_list", permanent=False)),
    path("", include("apps.ideas.urls")),
    path("", include("apps.agenda.urls")),
    path("gestion/admin/", admin.site.urls),
]
