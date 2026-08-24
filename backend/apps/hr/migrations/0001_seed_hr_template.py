"""
Seed the HR system SolutionTemplate (Phase P2.7) so HR is installable from the Solution Catalog
and the Create Solution Wizard out-of-the-box. Data-only migration (the hr app has no models);
depends on solution_templates. Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.hr.blueprint import seed_hr_template
    seed_hr_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="hr").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
