"""
Seed the Procurement system SolutionTemplate (Phase P2.5) so Procurement is installable from
the Solution Catalog and the Create Solution Wizard out-of-the-box. Data-only migration (the
procurement app has no models); depends on solution_templates having created its table.
Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.procurement.blueprint import seed_procurement_template
    seed_procurement_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="procurement").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
