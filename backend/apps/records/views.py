"""
Auto-generated CRUD API (Phase 1.9) — the metadata-driven factory.

One set of generic views serves EVERY entity, resolved at request time by
``entity_slug`` (entities are dynamic, so routes can't be registered statically).

Each endpoint (PROJECT_HANDBOOK.md §15) MUST and does:
  1. require an active workspace (``request.workspace_id`` / ``workspace_member``),
  2. read through NQL (never raw SQL) with workspace + soft-delete scoping,
  3. evaluate RBAC, then 4. ABAC per record,
  5. mask output fields. PostgreSQL RLS is the mandatory DB backstop.
"""
import json
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.computed.services import ComputedError
from apps.nql.exceptions import NQLError
from apps.permissions.services import PermissionError
from apps.rules.services import RuleBlocked

from .services import EntityNotQueryable, RecordNotFound, RecordService, resolve_entity


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _entity(request, entity_slug):
    try:
        return resolve_entity(_ws(request), entity_slug)
    except EntityNotQueryable as exc:
        raise NotFound(str(exc)) from exc


def _run(fn):
    """Map service-layer errors to HTTP responses."""
    try:
        return fn()
    except PermissionError as exc:
        raise PermissionDenied(str(exc)) from exc
    except RecordNotFound as exc:
        raise NotFound(str(exc)) from exc
    except (NQLError, RuleBlocked, ComputedError) as exc:
        raise ValidationError(str(exc)) from exc


class RecordListCreateView(APIView):
    def get(self, request, entity_slug):
        entity = _entity(request, entity_slug)
        member = _member(request)
        filter_source = None
        if "filter" in request.query_params:
            try:
                filter_source = json.loads(request.query_params["filter"])
            except (TypeError, ValueError) as exc:
                raise ParseError("filter must be valid JSON") from exc
        sort = []
        if request.query_params.get("sort"):
            for term in request.query_params["sort"].split(","):
                term = term.strip()
                if term:
                    desc = term.startswith("-")
                    sort.append({"field": term.lstrip("-+"), "direction": "desc" if desc else "asc"})
        limit = request.query_params.get("limit")
        offset = request.query_params.get("offset")
        rows = _run(lambda: RecordService.list_records(
            workspace_id=_ws(request), member=member, entity=entity,
            filter_source=filter_source, sort=sort or None,
            limit=int(limit) if limit else None, offset=int(offset) if offset else None))
        return Response({"results": rows, "count": len(rows)})

    def post(self, request, entity_slug):
        entity = _entity(request, entity_slug)
        rec = _run(lambda: RecordService.create_record(
            workspace_id=_ws(request), member=_member(request), entity=entity, data=request.data))
        return Response(rec, status=status.HTTP_201_CREATED)


class RecordDetailView(APIView):
    def get(self, request, entity_slug, record_id):
        entity = _entity(request, entity_slug)
        rec = _run(lambda: RecordService.retrieve_record(
            workspace_id=_ws(request), member=_member(request), entity=entity, record_id=record_id))
        return Response(rec)

    def patch(self, request, entity_slug, record_id):
        entity = _entity(request, entity_slug)
        rec = _run(lambda: RecordService.update_record(
            workspace_id=_ws(request), member=_member(request), entity=entity,
            record_id=record_id, data=request.data))
        return Response(rec)

    def delete(self, request, entity_slug, record_id):
        entity = _entity(request, entity_slug)
        _run(lambda: RecordService.delete_record(
            workspace_id=_ws(request), member=_member(request), entity=entity, record_id=record_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecordRestoreView(APIView):
    def post(self, request, entity_slug, record_id):
        entity = _entity(request, entity_slug)
        rec = _run(lambda: RecordService.restore_record(
            workspace_id=_ws(request), member=_member(request), entity=entity, record_id=record_id))
        return Response(rec)


class RecordTimelineView(APIView):
    """Per-record audit timeline built directly from the event store (master §42).

    GET /api/v1/data/{entity_slug}/{id}/timeline/ — every change, in order.
    """
    def get(self, request, entity_slug, record_id):
        from apps.eventstore.models import DomainEvent
        from apps.permissions import services as perm

        entity = _entity(request, entity_slug)
        member = _member(request)
        if not perm.check(member, entity, "read"):
            raise PermissionDenied(f"Not permitted to read {entity.slug}")
        events = (
            DomainEvent.objects
            .filter(workspace_id=_ws(request), aggregate_type="record", aggregate_id=record_id)
            .order_by("version", "global_sequence")
        )
        timeline = [{
            "event_type": e.event_type,
            "version": e.version,
            "occurred_at": e.occurred_at.isoformat(),
            "actor_id": str(e.actor_id) if e.actor_id else None,
            "changed_fields": list(((e.payload or {}).get("data") or {}).keys()),
        } for e in events]
        return Response({"events": timeline, "count": len(timeline)})
