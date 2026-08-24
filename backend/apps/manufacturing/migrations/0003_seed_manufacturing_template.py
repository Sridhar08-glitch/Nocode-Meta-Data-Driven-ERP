"""
Seed the Manufacturing system SolutionTemplate (Phase P2.12). Depends on solution_templates.
Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.manufacturing.blueprint import seed_manufacturing_template
    seed_manufacturing_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="manufacturing").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("manufacturing", "0002_manufacturing_rls"),
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
