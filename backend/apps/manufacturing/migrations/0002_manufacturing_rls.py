"""
Enable PostgreSQL Row-Level Security on every manufacturing table (PROJECT_HANDBOOK.md §2). No-op on SQLite.
"""
from django.db import migrations

PROTECTED_TABLES = [
    "mfg_work_centers", "mfg_boms", "mfg_bom_components", "mfg_routings", "mfg_routing_steps",
    "mfg_production_orders", "mfg_production_operations", "mfg_material_reservations",
    "mfg_production_costs", "mfg_quality_checks", "mfg_non_conformances", "mfg_mrp_runs",
    "mfg_mrp_results", "mfg_stock_lots",
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
        ("manufacturing", "0001_initial"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
