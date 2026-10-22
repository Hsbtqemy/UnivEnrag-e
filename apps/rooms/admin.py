from django.contrib import admin

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from .models import Room


@admin.register(Room)
class RoomAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "manage_rooms"
    list_display = ["name", "building", "capacity", "color", "order", "is_active"]
    list_editable = ["order", "is_active"]
    search_fields = ["name", "building"]

    def has_delete_permission(self, request, obj=None):
        return False  # une salle retirée se désactive : ses événements passés la citent
