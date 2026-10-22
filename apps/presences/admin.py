from django.contrib import admin

from .models import Presence


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    """Consultation seulement, par l'administrateur principal (données de localisation)."""

    list_display = ["day", "period", "actor", "place"]
    list_filter = ["period"]
    date_hierarchy = "day"
    search_fields = ["actor__display_name", "place"]

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser
