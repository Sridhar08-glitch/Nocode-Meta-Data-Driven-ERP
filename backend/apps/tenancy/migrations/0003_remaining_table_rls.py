"""
Phase 1.35 — RLS backfill.

Enables PostgreSQL Row-Level Security on EVERY remaining workspace-scoped table that was
not already covered by ``0002_static_table_rls.py`` or a per-app RLS migration, and is not
in the documented exemption list (workspaces / users / workspace_members / auth + session
tables / portal_* auth realm / event-store tables / global catalogs).

This closes the gap where feature apps from Phases 1.10–1.25 shipped ``workspace_id``
columns without the mandatory DB-layer backstop (PROJECT_HANDBOOK.md §2 "RLS mandatory"). Policy is
identical to 0002: a row is visible only when ``app.workspace_id`` matches, fail-closed when
the GUC is empty. No-op on SQLite. Bypassed under a superuser DB role (dev/CI); enforced
under the production non-superuser role.

The ``enable_rls`` function asserts each table has a ``workspace_id`` column before applying
the policy, so an incorrect table name fails loudly rather than silently skipping.
"""
from django.db import migrations

PROTECTED_TABLES = [
    # activity
    "activity_entries", "comments",
    # approvals
    "approval_processes", "approval_requests", "approval_decisions",
    # audit
    "audit_logs",
    # backups
    "backup_jobs", "restore_jobs", "data_retention_policies",
    # branding (incl. the SMTP secret-ref table)
    "workspace_branding", "email_smtp_configs",
    # computed
    "computed_field_cache", "computed_field_dependencies",
    # config VCS
    "config_commits", "config_branches", "config_merge_requests",
    # documents
    "document_folders", "documents", "document_versions", "document_shares",
    # integrations (incl. secret-bearing connector/oauth/inbound tables)
    "webhook_subscriptions", "webhook_deliveries", "oauth_apps",
    "http_connectors", "inbound_webhooks",
    # lineage
    "lineage_nodes", "lineage_edges",
    # localization (translation_keys is global → excluded)
    "workspace_locales", "translation_overrides", "entity_label_translations",
    # marketplace (plugins/versions are global → excluded)
    "installed_plugins",
    # notifications
    "notification_templates", "notifications", "notification_preferences", "push_subscriptions",
    # public forms
    "form_submissions",
    # records (read-model + versioning/locks)
    "records", "record_versions", "record_locks",
    # recycle bin
    "recycle_bin_entries",
    # reporting
    "reports", "report_snapshots", "dashboards", "dashboard_widgets",
    # rules
    "business_rules", "rule_execution_logs",
    # search
    "search_indexes", "saved_searches", "recent_searches",
    # sla
    "sla_policies", "business_hours", "sla_records",
    # staging (import/export)
    "import_jobs", "import_rows", "export_jobs",
    # tagging
    "tags", "record_tags", "document_tags",
    # tenancy sub-models (workspaces / workspace_members stay exempt)
    "organizations", "departments", "teams", "branches", "ip_allowlist",
    # saved views
    "saved_views",
    # workflows
    "workflow_definitions", "workflow_steps", "workflow_edges",
    "workflow_runs", "workflow_step_runs",
]

POLICY = "workspace_isolation"


def _has_workspace_id(cur, table) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s AND column_name='workspace_id'",
        [table])
    return cur.fetchone() is not None


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cur:
        for table in PROTECTED_TABLES:
            if not _has_workspace_id(cur, table):
                raise RuntimeError(
                    f"RLS backfill: table {table!r} is missing or has no workspace_id column")
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
    # Depend on each app's latest migration so every protected table already exists when
    # this runs (it lives in `tenancy`, so it naturally follows 0002 in that app).
    dependencies = [
        ("tenancy", "0002_static_table_rls"),
        ("activity", "0002_comment_is_pinned"),
        ("approvals", "0001_initial"),
        ("audit", "0001_initial"),
        ("backups", "0001_initial"),
        ("branding", "0001_initial"),
        ("computed", "0001_initial"),
        ("config_vcs", "0001_initial"),
        ("documents", "0001_initial"),
        ("integrations", "0001_initial"),
        ("lineage", "0001_initial"),
        ("localization", "0001_initial"),
        ("marketplace", "0001_initial"),
        ("notifications", "0001_initial"),
        ("public_forms", "0001_initial"),
        ("records", "0001_initial"),
        ("recyclebin", "0001_initial"),
        ("reporting", "0001_initial"),
        ("rules", "0001_initial"),
        ("search", "0001_initial"),
        ("sla", "0002_businesshours_region_businesshours_shifts_and_more"),
        ("staging", "0001_initial"),
        ("tagging", "0001_initial"),
        ("views_saved", "0001_initial"),
        ("workflows", "0001_initial"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
