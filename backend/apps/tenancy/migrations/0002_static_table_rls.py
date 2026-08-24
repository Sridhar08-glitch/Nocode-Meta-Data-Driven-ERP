"""
Enable PostgreSQL Row-Level Security on the workspace-scoped static config/data
tables (the mandatory DB-layer backstop behind ORM filtering — PROJECT_HANDBOOK.md §2/§8).

Policy mirrors the physical-table policy (apps/physical_tables/ddl.py): rows are
visible only when ``app.workspace_id`` matches, fail-closed when the GUC is empty.

Scope decision
--------------
RLS is applied to tables that are ALWAYS accessed inside a resolved workspace
context. The following are intentionally EXEMPT and must NOT get a restrictive
policy here, because they are read/written *before* a workspace context exists
(or are global / their own realm):

  - ``workspaces``               : the tenant root, looked up by slug to establish context
  - ``users``                    : global identity (a user spans many workspaces)
  - ``workspace_members``        : read by TenantMiddleware to verify membership *before* the GUC is set
  - auth/session tables          : refresh_token_families, api_keys, email_verification_tokens,
                                   password_reset_tokens, login_history, oauth_accounts (pre-context auth)
  - portal_* tables              : separate auth realm with its own scoping
  - event-store tables           : domain_events/command_log/etc. use the eventstore RLS helper

No-op on SQLite (RLS is PostgreSQL-only). Under a superuser DB role RLS is
bypassed, so this is safe to apply in dev/CI; it enforces under the production
non-superuser role.
"""
from django.db import migrations

PROTECTED_TABLES = [
    # metadata
    "entity_definitions", "field_definitions", "schema_versions", "modules",
    "entity_physical_tables", "view_definitions", "form_definitions",
    # relationships
    "relationship_definitions", "record_relationships",
    # permissions / RBAC
    "roles", "permissions", "data_masking_rules", "field_permissions",
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
        ("tenancy", "0001_initial"),
        ("metadata", "0002_fielddefinition_is_deleted"),
        ("relationships", "0001_initial"),
        ("permissions", "0001_initial"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
