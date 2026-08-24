from django.apps import AppConfig


class StagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.staging"
    label = "staging"
    verbose_name = "Staging"
