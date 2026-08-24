from django.apps import AppConfig


class FinancialKpisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.financial_kpis"
    label = "financial_kpis"

    def ready(self):
        # Register the native finance evaluators into the frozen analytics registry.
        from . import evaluators
        evaluators.register_all()
