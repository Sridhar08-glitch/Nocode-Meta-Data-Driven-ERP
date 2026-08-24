"""
Seed the Analytics & Intelligence system SolutionTemplate (Phase P2.13). Depends on
solution_templates. Idempotent; reversible. (Standard KPIs are seeded per-workspace via the
analytics ``/setup/`` endpoint, since KPIs are workspace-scoped.)
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.analytics.blueprint import seed_analytics_template
    seed_analytics_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="analytics").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0002_analytics_rls"),
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
