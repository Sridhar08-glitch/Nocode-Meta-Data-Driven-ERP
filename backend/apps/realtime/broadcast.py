"""
Realtime broadcast helpers (Phase 1.30).

Producers (RecordService, the workflow engine, dashboards) call these to push live
patches to workspace-scoped Channels groups. Group names embed the workspace id, so a
subscriber only ever receives its own tenant's events (RLS-aligned at the channel layer).

All pushes are best-effort: no channel layer (or a send failure) is swallowed so realtime
fan-out can never break the originating write. By default the push is deferred to
``transaction.on_commit`` so subscribers see committed state.
"""
from __future__ import annotations

import uuid

from django.db import transaction


def _ws_hex(workspace_id) -> str:
    wid = workspace_id if isinstance(workspace_id, uuid.UUID) else uuid.UUID(str(workspace_id))
    return wid.hex


def group_records(workspace_id) -> str:
    return f"ws_{_ws_hex(workspace_id)}_records"


def group_workflows(workspace_id) -> str:
    return f"ws_{_ws_hex(workspace_id)}_workflows"


def group_dashboards(workspace_id) -> str:
    return f"ws_{_ws_hex(workspace_id)}_dashboards"


def group_presence(workspace_id) -> str:
    return f"ws_{_ws_hex(workspace_id)}_presence"


def _send(group: str, message: dict) -> None:
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(group, message)
    except Exception:  # noqa: BLE001 — realtime fan-out must never break the write
        pass


def _deliver(group: str, message: dict, *, on_commit: bool) -> None:
    if on_commit:
        transaction.on_commit(lambda: _send(group, message))
    else:
        _send(group, message)


def broadcast_record(*, workspace_id, entity_slug, event_type, record_id,
                     data=None, actor_id=None, on_commit=True) -> None:
    """Push a ``record.*`` event to the workspace record stream."""
    _deliver(group_records(workspace_id), {
        "type": "record.event",
        "event": {
            "event_type": event_type,
            "entity_slug": entity_slug,
            "record_id": str(record_id),
            "data": data or {},
            "actor_id": str(actor_id) if actor_id else None,
        },
    }, on_commit=on_commit)


def broadcast_workflow(*, workspace_id, event_type, run_id, definition_id=None,
                       status=None, actor_id=None, on_commit=True) -> None:
    """Push a ``workflow.run.*`` event to the workspace workflow stream."""
    _deliver(group_workflows(workspace_id), {
        "type": "workflow.event",
        "event": {
            "event_type": event_type,
            "run_id": str(run_id),
            "definition_id": str(definition_id) if definition_id else None,
            "status": status,
            "actor_id": str(actor_id) if actor_id else None,
        },
    }, on_commit=on_commit)


def broadcast_dashboard(*, workspace_id, dashboard_id, payload=None, on_commit=True) -> None:
    """Push a dashboard-widget refresh to the workspace dashboard stream."""
    _deliver(group_dashboards(workspace_id), {
        "type": "dashboard.event",
        "event": {"dashboard_id": str(dashboard_id), "payload": payload or {}},
    }, on_commit=on_commit)
