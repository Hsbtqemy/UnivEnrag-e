from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.audit import audit
from apps.core.models import SiteSettings

from .capabilities import SuperuserAdminMixin
from .models import CAPABILITIES, User

# Les droits se cochent un par un ; les groupes Django ne servent pas ici. Les appareils
# de double authentification se gèrent par l'action « Réinitialiser » sur les comptes.
admin.site.unregister(Group)
admin.site.unregister(TOTPDevice)
admin.site.unregister(StaticDevice)


class CapabilitiesField(forms.MultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def __init__(self, **kwargs):
        super().__init__(
            choices=CAPABILITIES,
            required=False,
            label="Droits du gestionnaire",
            help_text="Sans effet pour l'administrateur principal, qui a tous les droits.",
            **kwargs,
        )


class CapabilitiesFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["capabilities"] = list(
                self.instance.user_permissions.filter(
                    content_type__app_label="accounts"
                ).values_list("codename", flat=True)
            )

    def save_capabilities(self, user):
        codes = self.cleaned_data.get("capabilities") or []
        permissions = Permission.objects.filter(
            content_type__app_label="accounts", codename__in=codes
        )
        user.user_permissions.set(permissions)


class ManagerCreationForm(CapabilitiesFormMixin, UserCreationForm):
    capabilities = CapabilitiesField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name"]


class ManagerChangeForm(CapabilitiesFormMixin, UserChangeForm):
    capabilities = CapabilitiesField()

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "is_active", "is_superuser"]


@admin.register(User)
class ManagerAdmin(SuperuserAdminMixin, UserAdmin):
    """Gestion des comptes : réservée à l'administrateur principal (CLAUDE.md ACC-4)."""

    form = ManagerChangeForm
    add_form = ManagerCreationForm
    list_display = ["username", "get_full_name", "role", "capability_list", "has_2fa", "is_active"]
    list_filter = ["is_active", "is_superuser"]
    fieldsets = [
        (None, {"fields": ["username", "password"]}),
        ("Identité", {"fields": ["first_name", "last_name"]}),
        (
            "Rôle",
            {
                "fields": ["is_active", "is_superuser", "capabilities"],
                "description": "Décocher « Actif » retire l'accès immédiatement.",
            },
        ),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "username",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "capabilities",
                ],
            },
        ),
    ]
    readonly_fields = ["last_login", "date_joined"]
    actions = ["reset_two_factor"]

    @admin.display(description="rôle")
    def role(self, obj):
        return "Administrateur principal" if obj.is_superuser else "Gestionnaire"

    @admin.display(description="droits")
    def capability_list(self, obj):
        if obj.is_superuser:
            return "tous"
        labels = dict(CAPABILITIES)
        codes = obj.user_permissions.filter(content_type__app_label="accounts").values_list(
            "codename", flat=True
        )
        return ", ".join(labels[c] for c in codes if c in labels) or "aucun"

    @admin.display(description="double authentification", boolean=True)
    def has_2fa(self, obj):
        return TOTPDevice.objects.filter(user=obj, confirmed=True).exists()

    def save_model(self, request, obj, form, change):
        obj.is_staff = True  # tout compte est un compte de gestion
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.save_capabilities(form.instance)
        audit.log(
            request.user,
            "accounts.manager_updated" if change else "accounts.manager_created",
            form.instance,
            capabilities=form.cleaned_data.get("capabilities") or [],
            is_active=form.instance.is_active,
            is_superuser=form.instance.is_superuser,
        )

    def has_delete_permission(self, request, obj=None):
        return False  # on désactive un compte, on ne le supprime pas (journal intact)

    @admin.action(description="Réinitialiser la double authentification (téléphone perdu)")
    def reset_two_factor(self, request, queryset):
        for user in queryset:
            TOTPDevice.objects.filter(user=user).delete()
            StaticDevice.objects.filter(user=user).delete()
            audit.log(request.user, "accounts.two_factor_reset", user)
        messages.success(
            request,
            "Double authentification réinitialisée : à la prochaine connexion, "
            "le compte devra la configurer de nouveau.",
        )


class SiteSettingsForm(forms.ModelForm):
    new_access_code = forms.CharField(
        label="Nouveau code d'accès",
        required=False,
        min_length=6,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text=(
            "Laisser vide pour garder le code actuel. Un nouveau code déconnecte tous les "
            "navigateurs : chacun devra saisir le nouveau."
        ),
    )
    regenerate_feeds_token = forms.BooleanField(
        label="Régénérer le jeton des flux iCal internes",
        required=False,
        help_text="Les abonnements existants cesseront de fonctionner.",
    )

    class Meta:
        model = SiteSettings
        fields = ["collective_name", "privacy_contact"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(SuperuserAdminMixin, admin.ModelAdmin):
    """Réglages du site : administrateur principal seulement (CLAUDE.md ACC-4)."""

    form = SiteSettingsForm
    readonly_fields = ["access_code_status", "updated_at"]
    fields = [
        "collective_name",
        "privacy_contact",
        "access_code_status",
        "new_access_code",
        "regenerate_feeds_token",
        "updated_at",
    ]

    @admin.display(description="code d'accès")
    def access_code_status(self, obj):
        return "défini" if obj.has_access_code else "aucun : la partie interne est fermée"

    def has_add_permission(self, request, *args):
        return False  # un seul exemplaire, créé à la demande

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied
        settings_obj = SiteSettings.get()
        return redirect("admin:core_sitesettings_change", settings_obj.pk)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get("new_access_code"):
            obj.set_access_code(form.cleaned_data["new_access_code"])
            audit.log(request.user, "core.access_code_changed", obj)
        if form.cleaned_data.get("regenerate_feeds_token"):
            obj.regenerate_feeds_token()
            audit.log(request.user, "core.feeds_token_regenerated", obj)
        changed = [f for f in ("collective_name", "privacy_contact") if f in form.changed_data]
        if changed:
            audit.log(request.user, "core.settings_changed", obj, fields=changed)
