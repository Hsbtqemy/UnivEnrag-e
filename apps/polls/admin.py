from django.contrib import admin

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from .models import Poll, PollSlot


class PollSlotInline(admin.TabularInline):
    model = PollSlot
    extra = 0
    can_delete = False


@admin.register(Poll)
class PollAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "manage_agenda"
    list_display = ["title", "owner", "is_closed", "event", "created_at"]
    list_filter = ["is_closed"]
    search_fields = ["title", "owner__display_name"]
    readonly_fields = ["owner", "event", "created_at"]
    fields = ["title", "description", "owner", "space", "room", "is_closed", "event", "created_at"]
    inlines = [PollSlotInline]

    def has_add_permission(self, request, *args):
        return False  # un sondage se crée depuis le site, sous un nom

    def has_delete_permission(self, request, obj=None):
        return False
