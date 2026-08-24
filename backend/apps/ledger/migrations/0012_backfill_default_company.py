"""
Default-company backfill (F11). For every workspace that already has journal entries, ensure a DEFAULT
``companies.Company`` and stamp its existing NULL-company journal entries with it — so historical books
become an explicit legal entity rather than relying on NULL. Idempotent + safe (only touches NULLs);
a no-op on a fresh database (no entries). Reversible = clear the stamped company_id (best-effort).

Going-forward postings that don't pass a company are still NULL = "the workspace's default company"
(justified: forcing every one of the 20+ certified packages to supply a company would break backward
compatibility and add a per-post lookup on the hot path); consolidation resolves NULL → default company.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    JournalEntry = apps.get_model("ledger", "JournalEntry")
    Company = apps.get_model("companies", "Company")
    workspace_ids = (JournalEntry.objects.filter(company_id__isnull=True)
                     .values_list("workspace_id", flat=True).distinct())
    for ws in list(workspace_ids):
        default = Company.objects.filter(workspace_id=ws, is_default=True).first()
        if default is None:
            default = Company.objects.create(
                workspace_id=ws, code="DEFAULT", name="Default Company", is_default=True)
        JournalEntry.objects.filter(workspace_id=ws, company_id__isnull=True).update(
            company_id=default.id)


def unbackfill(apps, schema_editor):
    JournalEntry = apps.get_model("ledger", "JournalEntry")
    Company = apps.get_model("companies", "Company")
    default_ids = set(Company.objects.filter(is_default=True).values_list("id", flat=True))
    if default_ids:
        JournalEntry.objects.filter(company_id__in=default_ids).update(company_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0011_ledger_rls"),
        ("companies", "0001_initial"),
    ]
    operations = [migrations.RunPython(backfill, unbackfill)]
