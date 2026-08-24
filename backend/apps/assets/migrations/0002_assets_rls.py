"""
Enable PostgreSQL Row-Level Security on the native asset tables (PROJECT_HANDBOOK.md §2). No-op on SQLite.
The asset master data is a framework metadata entity (RLS already enforced there); these are the
native depreciation/valuation/disposal tables.
"""
from django.db import migrations

PROTECTED_TABLES = [
    "asset_depreciation_schedules", "asset_depreciation_entries",
    "asset_valuation_snapshots", "asset_disposal_records",
]
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
        ("assets", "0001_initial"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
