"""
Enable PostgreSQL Row-Level Security on the native project tables (PROJECT_HANDBOOK.md §2). No-op on
SQLite. Project master data is a framework metadata entity (RLS enforced there); these are the
native cost-ledger / baseline tables.
"""
from django.db import migrations

PROTECTED_TABLES = ["project_cost_entries", "project_baselines"]
POLICY = "workspace_isolation"


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cur:
        for table in PROTECTED_TABLES:
            cur.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')
            cur.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS "{POLICY}" ON "{table}";')
            cur.execute(
                f'CREATE POLICY "{POLICY}" ON "{table}" '
                f"USING (workspace_id = "
                f"NULLIF(current_setting('app.workspace_id', TRUE), '')::uuid);"
            )


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cur:
        for table in PROTECTED_TABLES:
            cur.execute(f'DROP POLICY IF EXISTS "{POLICY}" ON "{table}";')
            cur.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY;')


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0001_initial"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
