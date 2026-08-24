"""
Seed the Projects & PSA system SolutionTemplate (Phase P2.10). Depends on solution_templates.
Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.projects.blueprint import seed_projects_template
    seed_projects_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="projects").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_projects_rls"),
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
