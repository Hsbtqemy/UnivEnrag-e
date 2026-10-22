from django.contrib import admin

from apps.accounts.capabilities import CapabilityAdminMixin, has_capability
from apps.audit.admin_mixins import AuditedAdminMixin

from .models import OpeningHours, Room


class OpeningHoursInline(admin.TabularInline):
    model = OpeningHours
    extra = 1

    def _allowed(self, request):
        return has_capability(request.user, "manage_rooms")

    def has_view_permission(self, request, obj=None):
        return self._allowed(request)

    def has_add_permission(self, request, obj=None):
        return self._allowed(request)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request)

    def has_delete_permission(self, request, obj=None):
        return self._allowed(request)


@admin.register(Room)
class RoomAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "manage_rooms"
    list_display = ["name", "building", "capacity", "booking_mode", "color", "order", "is_active"]
    list_editable = ["order", "is_active"]
    list_filter = ["booking_mode", "is_active"]
    search_fields = ["name", "building"]
    inlines = [OpeningHoursInline]
    fields = [
        "name",
        "building",
        "capacity",
        "color",
        "booking_mode",
        "access_notes",
        "order",
        "is_active",
    ]

    def has_delete_permission(self, request, obj=None):
        return False  # une salle retirée se désactive : ses événements passés la citent
