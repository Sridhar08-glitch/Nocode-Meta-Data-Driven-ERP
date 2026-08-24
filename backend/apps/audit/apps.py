from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit"

    def ready(self):
        # Register the wildcard audit projector with the event-store registry.
        from . import projections  # noqa: F401
