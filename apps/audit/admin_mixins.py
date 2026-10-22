from . import audit


class AuditedAdminMixin:
    """Trace dans le journal toute création ou modification faite depuis l'admin."""

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = "changed" if change else "created"
        audit.log(
            request.user,
            f"admin.{obj._meta.model_name}.{action}",
            obj,
            fields=list(form.changed_data),
        )
