"""
Enable PostgreSQL Row-Level Security on every payroll table (PROJECT_HANDBOOK.md §2 — salary
confidentiality is mandatory). Rows are visible only when ``app.workspace_id`` matches,
fail-closed when the GUC is empty. No-op on SQLite.
"""
from django.db import migrations

PROTECTED_TABLES = [
    "payroll_settings", "payroll_calendars", "payroll_salary_structures",
    "payroll_structure_components", "payroll_structure_assignments",
    "payroll_employee_profiles", "payroll_contracts", "payroll_periods",
    "payroll_runs", "payroll_payslips", "payroll_payslip_lines", "payroll_snapshots",
    "payroll_loans", "payroll_advances", "payroll_overtime", "payroll_adjustments",
    "payroll_final_settlements", "payroll_fx_rates", "payroll_cost_allocations",
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
        ("payroll", "0001_initial"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
