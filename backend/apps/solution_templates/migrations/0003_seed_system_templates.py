"""
Seed the shipped system solution templates (Phase P2.4A) so Sridhar ERP ships complete
solutions out-of-the-box. Idempotent (upsert by slug); reversible (removes only the
system rows it seeded).
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.solution_templates.seeding import seed_system_templates
    seed_system_templates()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(is_system=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("solution_templates", "0002_installed_solution_rls"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
