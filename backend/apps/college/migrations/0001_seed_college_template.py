"""
Seed the College Management system SolutionTemplate (College C1) so College is installable from
the Solution Catalog and the Create Solution Wizard. Data-only migration (the college app has no
models); depends on solution_templates. Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.college.blueprint import seed_college_template
    seed_college_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="college").delete()


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
