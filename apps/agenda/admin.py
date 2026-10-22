from django import forms
from django.contrib import admin

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from . import services
from .models import Event


class EventAdminForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "owner",
            "owner_email",
            "start",
            "end",
            "room",
            "place_text",
            "status",
            "is_public",
        ]

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        was_confirmed = self.instance.pk and self.instance.status == Event.Status.CONFIRMED
        if status == Event.Status.CONFIRMED and not was_confirmed:
            # La confirmation passe par le service : contrôle des salles et passage de la
            # proposition d'origine en « Planifiée ».
            raise forms.ValidationError("Confirmez l'événement depuis la page Programmation.")
        start, end = cleaned.get("start"), cleaned.get("end")
        if status == Event.Status.CONFIRMED and start and end:
            conflicts = services.room_conflicts(
                cleaned.get("room"), start, end, exclude_id=self.instance.pk
            )
            if conflicts.exists():
                raise forms.ValidationError(str(services.RoomConflictError(conflicts)))
        return cleaned


@admin.register(Event)
class EventAdmin(AuditedAdminMixin, CapabilityAdminMixin, admin.ModelAdmin):
    capability = "manage_agenda"
    form = EventAdminForm
    list_display = ["title", "start", "end", "room", "status", "is_public", "owner"]
    list_filter = ["status", "is_public", "room"]
    search_fields = ["title", "owner__display_name"]
    date_hierarchy = "start"
    readonly_fields = ["idea", "revision", "confirmed_at", "confirmed_by", "created_at"]

    def has_delete_permission(self, request, obj=None):
        return False  # on annule, on ne supprime pas (CLAUDE.md AGE-1)

    def save_model(self, request, obj, form, change):
        # Une modification dans l'admin périme la version affichée dans la programmation.
        if change:
            obj.revision += 1
        super().save_model(request, obj, form, change)
