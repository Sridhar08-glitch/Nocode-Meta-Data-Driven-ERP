"""
Seed the School Management system SolutionTemplate (P3.1) so School is installable from the
Solution Catalog and the Create Solution Wizard out-of-the-box. Data-only migration (the school
app has no models); depends on solution_templates. Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.school.blueprint import seed_school_template
    seed_school_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="school").delete()


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
