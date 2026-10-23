from django.contrib import admin
from django.utils.html import format_html

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from .models import Idea, IdeaSlot, Reaction


class IdeaSlotInline(admin.TabularInline):
    model = IdeaSlot
    extra = 0


class ReactionInline(admin.TabularInline):
    model = Reaction
    extra = 0
    readonly_fields = ["actor", "kind", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Idea)
class IdeaAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "moderate"
    list_display = [
        "title",
        "kind",
        "origin",
        "owner",
        "email_link",
        "status",
        "is_public",
        "created_at",
    ]
    list_filter = ["status", "is_public", "origin", "kind", "space", "wanted_room"]
    search_fields = ["title", "owner__display_name", "owner_email"]
    readonly_fields = ["tracking_token", "created_at", "moderated_at", "moderated_by"]
    inlines = [IdeaSlotInline, ReactionInline]

    @admin.display(description="e-mail")
    def email_link(self, obj):
        # Le site n'envoie rien (CLAUDE.md PUB-2) : le lien ouvre la messagerie de l'admin.
        if not obj.owner_email:
            return "—"
        return format_html('<a href="mailto:{0}">{0}</a>', obj.owner_email)

    def has_delete_permission(self, request, obj=None):
        return False  # on refuse, on ne supprime pas (CLAUDE.md MOD-1)
