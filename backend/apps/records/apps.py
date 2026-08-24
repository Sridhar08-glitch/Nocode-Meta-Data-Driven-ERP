from django.apps import AppConfig


class RecordsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.records"
    label = "records"
    verbose_name = "Records"

    def ready(self):
        from . import projections  # noqa: F401 — register record read-model projectors
