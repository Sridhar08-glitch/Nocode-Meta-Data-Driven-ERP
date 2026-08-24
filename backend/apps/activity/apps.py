from django.apps import AppConfig


class ActivityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.activity"
    label = "activity"
    verbose_name = "Activity"

    def ready(self):
        # Register the wildcard activity projector with the event-store registry.
        from . import projectors  # noqa: F401
