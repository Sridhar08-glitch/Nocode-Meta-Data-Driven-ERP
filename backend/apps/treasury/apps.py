from django.apps import AppConfig


class TreasuryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.treasury"
    label = "treasury"

    def ready(self):
        from .system_entity import register_system_entities
        register_system_entities()
