from django.apps import AppConfig


class SchemaRegistryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.schema_registry"
    label = "schema_registry"
    verbose_name = "Schema Registry"
