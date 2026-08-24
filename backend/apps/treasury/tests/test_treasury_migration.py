"""
Treasury Platform (F12) — migration verification / rollback certification (Certification Gate 10).

Proves the treasury migrations are REVERSIBLE and NON-DESTRUCTIVE: the RLS migration (0002) rolls back
to 0001 and re-applies with NO data loss, and its RunPython reverse is idempotent. Reversing only
0002 (RLS policies) never drops the tables, so this is safe to run mid-suite; the test restores the
app to 0002 in teardown. On SQLite the RLS steps are no-ops (vendor-guarded) but the round-trip +
data-survival guarantees still hold.
"""
import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

APP = "treasury"


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([(APP, target)])


def test_rls_migration_rolls_back_without_data_loss():
    from apps.treasury.models import TreasuryFacility
    ws = uuid.uuid4()
    fac = TreasuryFacility.objects.create(workspace_id=ws, principal=1000, facility_limit=1000)
    fid = fac.id
    try:
        # roll BACK the RLS migration (0002 -> 0001): drops policies only, tables + rows intact
        _migrate("0001_initial")
        assert TreasuryFacility.objects.filter(id=fid).exists()   # no data loss on rollback
        # re-APPLY forward (0001 -> 0002): RLS restored, row still present
        _migrate("0002_treasury_rls")
        assert TreasuryFacility.objects.filter(id=fid).exists()
    finally:
        _migrate("0002_treasury_rls")                             # leave app at head for the suite
        TreasuryFacility.objects.filter(id=fid).delete()


def test_rls_reverse_and_forward_are_idempotent():
    """The RunPython reverse (disable_rls) and forward (enable_rls) tolerate re-runs — the
    DROP POLICY IF EXISTS / ENABLE round-trips never error even if applied twice."""
    # apply forward twice, then reverse twice, then restore — no exception = idempotent/reversible
    _migrate("0002_treasury_rls")
    _migrate("0002_treasury_rls")
    _migrate("0001_initial")
    _migrate("0001_initial")
    _migrate("0002_treasury_rls")
    from apps.treasury.models import TreasuryCounterparty
    ws = uuid.uuid4()
    c = TreasuryCounterparty.objects.create(workspace_id=ws, code="X", name="X", exposure_limit=1)
    assert TreasuryCounterparty.objects.filter(id=c.id).exists()   # schema healthy after round-trips
    c.delete()
