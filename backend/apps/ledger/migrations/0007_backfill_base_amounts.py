"""
Multi-currency backfill: set every EXISTING journal line's base-currency amount equal to its
transaction amount (fx_rate defaults to 1, currency to base). Legacy single-currency data therefore
reports identically after ``account_balance`` switches to base-currency sums — the change is
transparent. Reversible (no-op on reverse; base_* simply becomes redundant for legacy rows).
"""
from django.db import migrations
from django.db.models import F


def backfill_base(apps, schema_editor):
    JournalLine = apps.get_model("ledger", "JournalLine")
    JournalLine.objects.all().update(base_debit=F("debit"), base_credit=F("credit"))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0006_journalline_base_credit_journalline_base_debit_and_more"),
    ]
    operations = [migrations.RunPython(backfill_base, noop)]
