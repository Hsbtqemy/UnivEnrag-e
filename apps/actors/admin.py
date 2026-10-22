from django.contrib import admin

from .models import Actor


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "created_at"]
    search_fields = ["display_name", "name_key"]
    readonly_fields = ["name_key", "created_at"]
    fields = ["display_name", "name_key", "user", "created_at"]

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
