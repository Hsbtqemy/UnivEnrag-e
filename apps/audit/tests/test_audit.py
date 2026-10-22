"""Journal d'activité des habilités (CLAUDE.md LOG-1)."""

import json

import pytest
from django.urls import reverse

from apps.audit import audit
from apps.audit.models import AuditLog
from apps.ideas import services as ideas_services

pytestmark = pytest.mark.django_db


def test_moderation_is_logged(make_idea, admin_user):
    idea = make_idea()
    ideas_services.accept(idea, user=admin_user)
    entry = AuditLog.objects.get()
    assert (entry.user, entry.action, entry.object_id) == (
        admin_user,
        "ideas.accepted",
        str(idea.pk),
    )


def test_programming_moves_are_logged_with_before_and_after(
    admin_client, make_idea, at, admin_user
):
    idea = make_idea(slots=[{"start": at(1, 10)}])
    ideas_services.accept(idea, user=admin_user)
    admin_client.post(
        reverse("agenda:gestion_move", args=[idea.event.pk]),
        json.dumps({"start": "2030-01-07T09:00:00", "end": "2030-01-07T11:00:00", "revision": 1}),
        content_type="application/json",
    )
    entry = AuditLog.objects.get(action="agenda.event_moved")
    assert entry.details["before"]["start"] != entry.details["after"]["start"]


def test_actions_without_account_are_not_logged(db, make_idea):
    assert audit.log(None, "test", make_idea()) is None
    assert not AuditLog.objects.exists()


def test_journal_is_append_only(admin_user):
    entry = audit.log(admin_user, "test.action")
    entry.action = "autre"
    with pytest.raises(ValueError):
        entry.save()
    with pytest.raises(ValueError):
        entry.delete()


def test_admin_changes_are_logged(admin_client, room):
    admin_client.post(
        f"/gestion/admin/rooms/room/{room.pk}/change/",
        {
            "name": "Salle renommée",
            "building": "",
            "capacity": "",
            "color": "#123456",
            "order": 0,
            "is_active": "on",
        },
    )
    entry = AuditLog.objects.get(action="admin.room.changed")
    assert "name" in entry.details["fields"]


def test_access_code_change_is_logged(admin_client, site):
    admin_client.post(
        f"/gestion/admin/core/sitesettings/{site.pk}/change/",
        {"collective_name": site.collective_name, "new_access_code": "nouveau-code-2026"},
    )
    assert AuditLog.objects.filter(action="core.access_code_changed").exists()
    site.refresh_from_db()
    assert site.check_access_code("nouveau-code-2026")
