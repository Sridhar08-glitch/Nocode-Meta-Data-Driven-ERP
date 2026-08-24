"""
Seed the Asset Management system SolutionTemplate (Phase P2.9). Depends on solution_templates.
Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.assets.blueprint import seed_assets_template
    seed_assets_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="assets").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_assets_rls"),
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
