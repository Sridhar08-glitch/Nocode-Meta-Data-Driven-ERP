"""
Runtime RLS helper — set/clear the PostgreSQL ``app.workspace_id`` session GUC
that Row-Level Security policies read.

This is the runtime counterpart to ``physical_tables.ddl.build_rls_sql`` (which
emits the *policies*). Use it anywhere tenant-scoped queries run **outside** the
request/middleware path — Celery tasks, management commands, the Phase 1.9 API
factory, projection rebuilds, data backfills.

All functions are no-ops on non-PostgreSQL backends (e.g. SQLite in tests), where
RLS does not exist. They return ``True`` when a GUC operation actually ran.
"""
from contextlib import contextmanager

from django.db import connection

GUC = "app.workspace_id"


def set_workspace(workspace_id) -> bool:
    """SET app.workspace_id for the current connection. Returns True if applied."""
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cur:
        cur.execute(f"SET {GUC} = %s", [str(workspace_id)])
    return True


def clear_workspace() -> bool:
    """RESET app.workspace_id (fail-closed: empty GUC ⇒ RLS returns no rows)."""
    if connection.vendor != "postgresql" or connection.connection is None:
        return False
    with connection.cursor() as cur:
        cur.execute(f"RESET {GUC}")
    return True


def get_current_workspace():
    """Return the current app.workspace_id GUC value, or None if unset."""
    if connection.vendor != "postgresql":
        return None
    with connection.cursor() as cur:
        cur.execute(f"SELECT current_setting('{GUC}', TRUE)")
        value = cur.fetchone()[0]
    return value or None


@contextmanager
def workspace_context(workspace_id):
    """
    Scope a block of tenant-aware work to *workspace_id*.

    On PostgreSQL the GUC is set on entry and cleared on exit (even on error), so
    background jobs and the API factory get the same RLS isolation as HTTP requests.
    On SQLite this is an inert no-op.

    Example::

        with workspace_context(ws_id):
            Record.objects.filter(...)  # RLS-scoped on PostgreSQL
    """
    set_workspace(workspace_id)
    try:
        yield
    finally:
        clear_workspace()
