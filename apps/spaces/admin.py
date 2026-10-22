from django.contrib import admin

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from .models import Space


@admin.register(Space)
class SpaceAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "manage_spaces"
    list_display = ["name", "description", "color", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}

    def has_delete_permission(self, request, obj=None):
        return False  # un espace terminé s'archive (CDC §5)
