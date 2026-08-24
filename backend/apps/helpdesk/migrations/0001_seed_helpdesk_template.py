"""
Seed the Helpdesk & ITSM system SolutionTemplate (Phase P2.11). The helpdesk app is model-less
(it reuses the SLA engine + framework metadata), so this data-only migration is its only one.
Depends on solution_templates. Idempotent; reversible.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.helpdesk.blueprint import seed_helpdesk_template
    seed_helpdesk_template()


def unseed(apps, schema_editor):
    SolutionTemplate = apps.get_model("solution_templates", "SolutionTemplate")
    SolutionTemplate.objects.filter(slug="helpdesk").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("solution_templates", "0003_seed_system_templates"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
