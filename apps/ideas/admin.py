from django.contrib import admin
from django.utils.html import format_html

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from .models import Idea, IdeaSlot


class IdeaSlotInline(admin.TabularInline):
    model = IdeaSlot
    extra = 0


@admin.register(Idea)
class IdeaAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "moderate"
    list_display = ["title", "owner", "email_link", "status", "created_at"]
    list_filter = ["status", "wanted_room"]
    search_fields = ["title", "owner__display_name", "owner_email"]
    readonly_fields = ["tracking_token", "created_at", "moderated_at", "moderated_by"]
    inlines = [IdeaSlotInline]

    @admin.display(description="e-mail")
    def email_link(self, obj):
        # Le site n'envoie rien (CLAUDE.md PUB-2) : le lien ouvre la messagerie de l'admin.
        return format_html('<a href="mailto:{0}">{0}</a>', obj.owner_email)

    def has_delete_permission(self, request, obj=None):
        return False  # on refuse, on ne supprime pas (CLAUDE.md MOD-1)
