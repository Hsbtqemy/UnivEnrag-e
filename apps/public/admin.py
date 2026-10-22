from django.contrib import admin, messages
from django.utils.html import format_html

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from . import services
from .models import ContactMessage, NewsPost


@admin.register(NewsPost)
class NewsPostAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "manage_public"
    list_display = ["title", "is_published", "published_at", "author"]
    list_filter = ["is_published"]
    search_fields = ["title", "summary", "body"]
    prepopulated_fields = {"slug": ["title"]}
    fields = ["title", "slug", "summary", "body", "is_published", "published_at"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False  # on dépublie, on ne supprime pas (CLAUDE.md MOD-1)


@admin.register(ContactMessage)
class ContactMessageAdmin(CapabilityAdminMixin, admin.ModelAdmin):
    capability = "manage_public"
    list_display = ["created_at", "sender", "email_link", "excerpt", "handled"]
    list_filter = [("handled_at", admin.EmptyFieldListFilter)]
    search_fields = ["sender__display_name", "email", "message"]
    readonly_fields = ["sender", "email_link", "message", "created_at", "handled_at", "handled_by"]
    fields = readonly_fields
    actions = ["mark_handled"]

    @admin.display(description="e-mail")
    def email_link(self, obj):
        # Le site n'envoie rien : le lien ouvre la messagerie de la personne qui répond.
        if not obj.email:
            return "— (pas d'adresse laissée)"
        return format_html('<a href="mailto:{0}">{0}</a>', obj.email)

    @admin.display(description="message")
    def excerpt(self, obj):
        return obj.message if len(obj.message) <= 80 else f"{obj.message[:77]}…"

    @admin.display(description="traité", boolean=True)
    def handled(self, obj):
        return obj.is_handled

    @admin.action(description="Marquer comme traité")
    def mark_handled(self, request, queryset):
        for message in queryset:
            services.mark_handled(message, user=request.user)
        self.message_user(request, f"{queryset.count()} message(s) traité(s).", messages.SUCCESS)

    def has_add_permission(self, request, *args):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # effacés au bout d'un an par purge_contact_messages
