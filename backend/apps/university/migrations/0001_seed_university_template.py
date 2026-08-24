"""
Seed the University Management system SolutionTemplate (University U1) so University is installable
from the Solution Catalog and the Create Solution Wizard. Data-only migration (the university app has
no models); depends on solution_templates. Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.university.blueprint import seed_university_template
    seed_university_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="university").delete()


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
