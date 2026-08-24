from django.apps import AppConfig


class PersonalizationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.personalization"
    label = "personalization"
    verbose_name = "User Personalization"
