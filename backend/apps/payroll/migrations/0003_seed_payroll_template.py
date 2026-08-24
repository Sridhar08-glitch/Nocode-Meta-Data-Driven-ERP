"""
Seed the Payroll system SolutionTemplate (Phase P2.8) so Payroll is installable from the
Solution Catalog and the Create Solution Wizard. Depends on solution_templates. Idempotent.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.payroll.blueprint import seed_payroll_template
    seed_payroll_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="payroll").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0002_payroll_rls"),
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
