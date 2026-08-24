"""
Treasury Platform (F12) — PostgreSQL RLS enforcement certification (Certification Gate 9).

Proves the treasury tables actually isolate tenants at the DATABASE layer under a NON-superuser role
(dev/CI runs as superuser → RLS is bypassed, so ORM-level tests alone can't prove the backstop).
Mirrors apps/tenancy/tests/test_backfill_rls.py. Skipped on SQLite (RLS is PostgreSQL-only).
"""
import uuid

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db(transaction=True)

TABLES = ["treasury_counterparties", "treasury_facilities",
          "treasury_investments", "treasury_transactions"]


def _seed(table, ws):
    if table == "treasury_counterparties":
        from apps.treasury.models import TreasuryCounterparty
        TreasuryCounterparty.objects.create(workspace_id=ws, code="C", name="C", exposure_limit=1)
    elif table == "treasury_facilities":
        from apps.treasury.models import TreasuryFacility
        TreasuryFacility.objects.create(workspace_id=ws, principal=1, facility_limit=1)
    elif table == "treasury_investments":
        from apps.treasury.models import TreasuryInvestment
        TreasuryInvestment.objects.create(workspace_id=ws, principal=1, face_value=1, outstanding=1)
    else:
        from apps.treasury.models import TreasuryTransaction
        TreasuryTransaction.objects.create(workspace_id=ws, transaction_type="fee", amount=1)


@pytest.mark.parametrize("table", TABLES)
def test_treasury_rls_enforced_under_app_role(table):
    if connection.vendor != "postgresql":
        pytest.skip("RLS is PostgreSQL-only")
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    _seed(table, ws_a)
    _seed(table, ws_b)

    import psycopg2

    role = f"nexus_tr_{table}"
    with connection.cursor() as cur:
        cur.execute(f"DROP ROLE IF EXISTS {role}")
        cur.execute(f"CREATE ROLE {role} LOGIN PASSWORD 'pw' NOSUPERUSER NOBYPASSRLS")
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        cur.execute(f'GRANT SELECT ON "{table}" TO {role}')

    dbname = connection.settings_dict["NAME"]
    app = psycopg2.connect(host="localhost", port=5432, user=role, password="pw", dbname=dbname)
    app.autocommit = True
    ac = app.cursor()
    try:
        ac.execute("SET app.workspace_id = %s", [str(ws_a)])
        ac.execute(f'SELECT count(*) FROM "{table}"')
        assert ac.fetchone()[0] == 1                          # only ws_a's row visible
        ac.execute("RESET app.workspace_id")
        ac.execute(f'SELECT count(*) FROM "{table}"')
        assert ac.fetchone()[0] == 0                          # fail-closed when the GUC is unset
    finally:
        app.close()
        with connection.cursor() as cur:
            cur.execute(f'REVOKE ALL ON "{table}" FROM {role}')
            cur.execute(f"REVOKE USAGE ON SCHEMA public FROM {role}")
            cur.execute(f"DROP ROLE IF EXISTS {role}")
