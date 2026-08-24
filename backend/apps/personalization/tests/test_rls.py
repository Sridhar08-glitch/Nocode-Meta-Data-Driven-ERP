"""
Proves the user_preferences RLS policy (migration 0002) isolates tenants on PostgreSQL
under a non-superuser role. Skipped on SQLite (no RLS). Mirrors
apps/feature_flags/tests/test_rls.py.
"""
import uuid

import pytest
from django.db import connection

from apps.personalization.models import UserPreference

pytestmark = pytest.mark.django_db(transaction=True)


def test_user_preferences_rls_enforced_under_app_role():
    if connection.vendor != "postgresql":
        pytest.skip("RLS is PostgreSQL-only")
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    UserPreference.objects.create(workspace_id=ws_a, user_id=uuid.uuid4(), values={"density": "compact"})
    UserPreference.objects.create(workspace_id=ws_b, user_id=uuid.uuid4(), values={})

    import psycopg2

    with connection.cursor() as cur:
        cur.execute("DROP ROLE IF EXISTS nexus_pref_rls_test")
        cur.execute("CREATE ROLE nexus_pref_rls_test LOGIN PASSWORD 'pw' NOSUPERUSER NOBYPASSRLS")
        cur.execute("GRANT USAGE ON SCHEMA public TO nexus_pref_rls_test")
        cur.execute("GRANT SELECT ON user_preferences TO nexus_pref_rls_test")

    dbname = connection.settings_dict["NAME"]
    app = psycopg2.connect(host="localhost", port=5432, user="nexus_pref_rls_test",
                           password="pw", dbname=dbname)
    app.autocommit = True
    ac = app.cursor()
    try:
        ac.execute("SET app.workspace_id = %s", [str(ws_a)])
        ac.execute("SELECT count(*) FROM user_preferences")
        assert ac.fetchone()[0] == 1                       # only ws_a visible
        ac.execute("RESET app.workspace_id")
        ac.execute("SELECT count(*) FROM user_preferences")
        assert ac.fetchone()[0] == 0                       # fail-closed when unset
    finally:
        app.close()
        with connection.cursor() as cur:
            cur.execute("REVOKE ALL ON user_preferences FROM nexus_pref_rls_test")
            cur.execute("REVOKE USAGE ON SCHEMA public FROM nexus_pref_rls_test")
            cur.execute("DROP ROLE IF EXISTS nexus_pref_rls_test")
