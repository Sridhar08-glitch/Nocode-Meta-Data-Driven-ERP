"""
Phase 1.35 — proves the RLS backfill (tenancy/0003) actually isolates tenants on
PostgreSQL under a non-superuser role, across a representative high-risk sample of the
backfilled tables (a secret-ref table, an OAuth secret table, a workflow table, a report).
Skipped on SQLite (no RLS). Mirrors apps/tenancy/tests/test_static_rls.py.
"""
import uuid

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db(transaction=True)


def _make_email_smtp(ws):
    from apps.branding.models import EmailSMTPConfig
    EmailSMTPConfig.objects.create(
        workspace_id=ws, host="smtp.example.com", username="u",
        password_ref="ref", from_email="from@example.com")


def _make_oauth_app(ws):
    from apps.integrations.models import OAuthApp
    OAuthApp.objects.create(
        workspace_id=ws, name="App", provider="google",
        client_id="cid", client_secret_ref="ref")


def _make_workflow(ws):
    from apps.workflows.models import WorkflowDefinition
    WorkflowDefinition.objects.create(
        workspace_id=ws, name="WF", slug="wf", trigger_type="manual")


def _make_report(ws):
    from apps.reporting.models import Report
    Report.objects.create(workspace_id=ws, name="R", slug="r", nql_ast={"entity": "x"})


CASES = [
    ("email_smtp_configs", _make_email_smtp),
    ("oauth_apps", _make_oauth_app),
    ("workflow_definitions", _make_workflow),
    ("reports", _make_report),
]


@pytest.mark.parametrize("table,make", CASES)
def test_backfill_rls_enforced_under_app_role(table, make):
    if connection.vendor != "postgresql":
        pytest.skip("RLS is PostgreSQL-only")
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    make(ws_a)
    make(ws_b)

    import psycopg2

    role = f"nexus_bf_{table}"
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
        assert ac.fetchone()[0] == 1                      # only ws_a's row visible
        ac.execute("RESET app.workspace_id")
        ac.execute(f'SELECT count(*) FROM "{table}"')
        assert ac.fetchone()[0] == 0                      # fail-closed when GUC unset
    finally:
        app.close()
        with connection.cursor() as cur:
            cur.execute(f'REVOKE ALL ON "{table}" FROM {role}')
            cur.execute(f"REVOKE USAGE ON SCHEMA public FROM {role}")
            cur.execute(f"DROP ROLE IF EXISTS {role}")
