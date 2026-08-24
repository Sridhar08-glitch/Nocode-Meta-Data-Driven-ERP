"""
Proves the static-table RLS policy (migration 0002) actually isolates tenants on
PostgreSQL under a non-superuser role. Skipped on SQLite (no RLS).
"""
import uuid

import pytest
from django.db import connection

from apps.metadata.models import EntityDefinition

# transaction=True so the test role + rows actually COMMIT and are visible to the
# separate (non-superuser) psycopg2 connection used to prove RLS enforcement.
pytestmark = pytest.mark.django_db(transaction=True)


def _pg_only():
    if connection.vendor != "postgresql":
        pytest.skip("RLS is PostgreSQL-only")


def test_entity_definitions_rls_enforced_under_app_role():
    _pg_only()
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    EntityDefinition.objects.create(workspace_id=ws_a, slug="a_ent", name="A", plural_name="As")
    EntityDefinition.objects.create(workspace_id=ws_b, slug="b_ent", name="B", plural_name="Bs")

    import psycopg2

    with connection.cursor() as cur:
        cur.execute("DROP ROLE IF EXISTS nexus_rls_test")
        cur.execute("CREATE ROLE nexus_rls_test LOGIN PASSWORD 'pw' NOSUPERUSER NOBYPASSRLS")
        cur.execute("GRANT USAGE ON SCHEMA public TO nexus_rls_test")
        cur.execute("GRANT SELECT ON entity_definitions TO nexus_rls_test")

    dbname = connection.settings_dict["NAME"]
    app = psycopg2.connect(host="localhost", port=5432, user="nexus_rls_test",
                           password="pw", dbname=dbname)
    app.autocommit = True
    ac = app.cursor()
    try:
        ac.execute("SET app.workspace_id = %s", [str(ws_a)])
        ac.execute("SELECT count(*) FROM entity_definitions")
        assert ac.fetchone()[0] == 1                      # only ws_a visible
        ac.execute("RESET app.workspace_id")
        ac.execute("SELECT count(*) FROM entity_definitions")
        assert ac.fetchone()[0] == 0                      # fail-closed when unset
    finally:
        app.close()
        with connection.cursor() as cur:
            cur.execute("REVOKE ALL ON entity_definitions FROM nexus_rls_test")
            cur.execute("REVOKE USAGE ON SCHEMA public FROM nexus_rls_test")
            cur.execute("DROP ROLE IF EXISTS nexus_rls_test")
