from django.contrib import admin

from .models import Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["name", "building", "capacity", "color", "order", "is_active"]
    list_editable = ["order", "is_active"]
    search_fields = ["name", "building"]
