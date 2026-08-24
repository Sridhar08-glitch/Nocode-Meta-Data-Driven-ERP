"""
Proves the feature-flag RLS policy (migration 0002) isolates tenants on PostgreSQL
under a non-superuser role. Skipped on SQLite (no RLS). Mirrors
apps/tenancy/tests/test_static_rls.py.
"""
import uuid

import pytest
from django.db import connection

from apps.feature_flags.models import FeatureFlag

pytestmark = pytest.mark.django_db(transaction=True)


def test_feature_flags_rls_enforced_under_app_role():
    if connection.vendor != "postgresql":
        pytest.skip("RLS is PostgreSQL-only")
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    FeatureFlag.objects.create(workspace_id=ws_a, key="a_flag", enabled=True)
    FeatureFlag.objects.create(workspace_id=ws_b, key="b_flag", enabled=True)

    import psycopg2

    with connection.cursor() as cur:
        cur.execute("DROP ROLE IF EXISTS nexus_ff_rls_test")
        cur.execute("CREATE ROLE nexus_ff_rls_test LOGIN PASSWORD 'pw' NOSUPERUSER NOBYPASSRLS")
        cur.execute("GRANT USAGE ON SCHEMA public TO nexus_ff_rls_test")
        cur.execute("GRANT SELECT ON feature_flags TO nexus_ff_rls_test")

    dbname = connection.settings_dict["NAME"]
    app = psycopg2.connect(host="localhost", port=5432, user="nexus_ff_rls_test",
                           password="pw", dbname=dbname)
    app.autocommit = True
    ac = app.cursor()
    try:
        ac.execute("SET app.workspace_id = %s", [str(ws_a)])
        ac.execute("SELECT count(*) FROM feature_flags")
        assert ac.fetchone()[0] == 1                       # only ws_a visible
        ac.execute("RESET app.workspace_id")
        ac.execute("SELECT count(*) FROM feature_flags")
        assert ac.fetchone()[0] == 0                       # fail-closed when unset
    finally:
        app.close()
        with connection.cursor() as cur:
            cur.execute("REVOKE ALL ON feature_flags FROM nexus_ff_rls_test")
            cur.execute("REVOKE USAGE ON SCHEMA public FROM nexus_ff_rls_test")
            cur.execute("DROP ROLE IF EXISTS nexus_ff_rls_test")
