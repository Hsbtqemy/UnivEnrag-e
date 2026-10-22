from django.contrib import admin, messages

from . import services
from .models import Actor


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "created_at", "anonymized_at"]
    search_fields = ["display_name", "name_key"]
    readonly_fields = ["name_key", "created_at", "anonymized_at"]
    fields = ["display_name", "name_key", "user", "created_at", "anonymized_at"]
    actions = ["anonymize"]

    @admin.action(description="Anonymiser (droit d'effacement, irréversible)")
    def anonymize(self, request, queryset):
        from apps.audit import audit  # le journal dépend des acteurs, pas l'inverse

        count = 0
        for actor in queryset.filter(anonymized_at__isnull=True):
            services.anonymize(actor)
            # Le journal garde le geste, pas le nom (décision 17).
            audit.log(request.user, "actors.anonymized", actor)
            count += 1
        self.message_user(
            request,
            f"{count} personne(s) anonymisée(s). Vérifiez à la main les champs libres : "
            "e-mail du porteur d'une proposition, intervenants pressentis.",
            messages.SUCCESS,
        )

    # Les personnes et leur rattachement à un compte : administrateur principal seulement.
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False  # un acteur naît d'une contribution, jamais à la main

    def has_delete_permission(self, request, obj=None):
        return False
