from django.apps import AppConfig


class ComputedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.computed"
    label = "computed"
    verbose_name = "Computed"
