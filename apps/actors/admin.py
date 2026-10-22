from django.contrib import admin

from .models import Actor


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "created_at"]
    search_fields = ["display_name", "name_key"]
    readonly_fields = ["name_key", "created_at"]
    fields = ["display_name", "name_key", "user", "created_at"]
