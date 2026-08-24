"""
PostgreSQL Row-Level Security context helpers.

Every request sets:
    SET LOCAL app.workspace_id = '<uuid>';

This is picked up by the current_workspace_id() function defined in
setup_postgres.sql and used by all RLS policies.

Usage:
    from apps.eventstore.rls import set_workspace_rls, workspace_rls_context

    # In middleware (sets for the whole transaction / request):
    set_workspace_rls(str(workspace_id))

    # As a context manager for isolated operations:
    with workspace_rls_context(workspace_id):
        ...
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

from django.db import connection


def _is_postgres() -> bool:
    return connection.vendor == "postgresql"


def set_workspace_rls(workspace_id: str | uuid.UUID) -> None:
    """
    Execute SET LOCAL app.workspace_id = '...' on the current connection.

    'SET LOCAL' scopes the setting to the current transaction, which is
    exactly what we want — it resets automatically when the transaction ends.

    Must be called inside an active transaction.

    No-op on non-PostgreSQL backends (e.g. SQLite in tests).
    """
    safe_id = str(workspace_id)
    # Basic sanity check — must be a valid UUID string.
    uuid.UUID(safe_id)  # raises ValueError for garbage input
    if not _is_postgres():
        return
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.workspace_id = %s", [safe_id])


def clear_workspace_rls() -> None:
    """Reset the workspace context (sets to empty string).

    No-op on non-PostgreSQL backends.
    """
    if not _is_postgres():
        return
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.workspace_id = ''")


@contextmanager
def workspace_rls_context(workspace_id: str | uuid.UUID):
    """
    Context manager that sets the RLS workspace for an atomic block.

    Usage:
        with transaction.atomic():
            with workspace_rls_context(ws_id):
                Record.objects.create(...)
    """
    set_workspace_rls(workspace_id)
    try:
        yield
    finally:
        clear_workspace_rls()


def get_current_workspace_id() -> uuid.UUID | None:
    """
    Read the current app.workspace_id from PostgreSQL session config.
    Returns None if not set (e.g. in tests without a request context, or on SQLite).
    """
    if not _is_postgres():
        return None
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.workspace_id', true)")
        row = cursor.fetchone()
    if row and row[0]:
        try:
            return uuid.UUID(row[0])
        except (ValueError, AttributeError):
            return None
    return None
