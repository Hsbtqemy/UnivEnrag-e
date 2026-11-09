from django import forms
from django.contrib import admin

from apps.accounts.capabilities import CapabilityAdminMixin
from apps.audit.admin_mixins import AuditedAdminMixin

from . import history, services
from .models import Event, EventChange


class EventAdminForm(forms.ModelForm):
    visio_link = forms.URLField(label="Lien visio", required=False, assume_scheme="https")

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
            "visio_link",
            "is_public",
            "public_requested",
            "is_locked",
        ]

    def clean(self):
        cleaned = super().clean()
        # Le statut se change sur la fiche de l'événement (menu « Statut », décision 26) :
        # contrôle des salles, idée d'origine, historique. Ici, on garde seulement la règle
        # des salles pour un événement déjà confirmé qu'on déplace.
        start, end = cleaned.get("start"), cleaned.get("end")
        if self.instance.status == Event.Status.CONFIRMED and start and end:
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
    readonly_fields = [
        "status",
        "idea",
        "revision",
        "confirmed_at",
        "confirmed_by",
        "created_at",
    ]

    def get_queryset(self, request):
        return Event.all_objects.all()  # masqués compris (décision 26)

    def has_delete_permission(self, request, obj=None):
        # La suppression passe par la fiche de l'événement, qui la journalise et met
        # l'idée d'origine à jour (décision 26).
        return False

    def save_model(self, request, obj, form, change):
        # Une modification dans l'admin périme la version affichée dans la programmation,
        # et entre dans l'historique comme toute autre (CLAUDE.md AGE-4).
        before = history.snapshot(Event.all_objects.get(pk=obj.pk)) if change else {}
        if change:
            obj.revision += 1
        super().save_model(request, obj, form, change)
        action = EventChange.Action.UPDATED if change else EventChange.Action.CREATED
        history.record(obj, action, user=request.user, before=before)
