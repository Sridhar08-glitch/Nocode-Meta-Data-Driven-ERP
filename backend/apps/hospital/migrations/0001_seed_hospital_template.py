"""
Seed the Hospital Management system SolutionTemplate (Hospital H1) so Hospital is installable from the
Solution Catalog and the Create Solution Wizard. Data-only migration (the hospital app has no models);
depends on solution_templates. Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.hospital.blueprint import seed_hospital_template
    seed_hospital_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="hospital").delete()


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
