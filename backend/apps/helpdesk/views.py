"""
Helpdesk / ITSM REST API (Phase P2.11) at /api/v1/helpdesk/.

Ticket + ITSM lifecycle runs as the real workspace member (RBAC/ABAC/RLS apply). SLA timers reuse
the P1.19 engine; the assignment/escalation/knowledge/CSAT engines are deterministic.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.solution_templates.documents import SolutionDocumentService as Docs

from .blueprint import HELPDESK_OBJECTS
from .services import (
    AssignmentService,
    CSATService,
    EscalationService,
    HelpdeskError,
    KnowledgeService,
    TicketService,
)

_ADMIN_ROLES = {"owner", "admin"}


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


def _require_admin(request):
    if getattr(_member(request), "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("This action requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _kw(request):
    return {"workspace_id": _ws(request), "member": _member(request), "actor_id": _uid(request)}


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        TicketService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Helpdesk numbering ready."})


class DocumentCreate(APIView):
    """Create any helpdesk object. Tickets go through TicketService (numbering + SLA attach)."""

    def post(self, request, entity_slug):
        if entity_slug not in HELPDESK_OBJECTS:
            return Response({"detail": "Unknown helpdesk object."}, status=404)
        if entity_slug == "ticket":
            rec = TicketService.create_ticket(data=request.data or {}, **_kw(request))
        else:
            rec = Docs.create(workspace_id=_ws(request), entity_slug=entity_slug,
                              data=request.data or {}, member=_member(request),
                              actor_id=_uid(request))
        return Response(rec, status=201)


class TicketAssign(APIView):
    def post(self, request, pk):
        d = request.data or {}
        return Response(TicketService.assign_ticket(
            record_id=pk, agent=d.get("agent"), team=d.get("team", ""), **_kw(request)))


class TicketAutoAssign(APIView):
    def post(self, request, pk):
        d = request.data or {}
        try:
            return Response(AssignmentService.auto_assign(
                record_id=pk, method=d.get("method", "load_based"), team=d.get("team", ""),
                skill=d.get("skill", ""), **_kw(request)))
        except HelpdeskError as exc:
            return Response({"detail": str(exc)}, status=400)


class TicketEscalate(APIView):
    def post(self, request, pk):
        return Response(EscalationService.escalate(record_id=pk, **_kw(request)))


class TicketStatus(APIView):
    def post(self, request, pk):
        status = (request.data or {}).get("status")
        if not status:
            return Response({"detail": "status is required."}, status=400)
        return Response(TicketService.set_status(record_id=pk, status=status, **_kw(request)))


class TicketResolve(APIView):
    def post(self, request, pk):
        return Response(TicketService.resolve_ticket(record_id=pk, **_kw(request)))


class TicketClose(APIView):
    def post(self, request, pk):
        return Response(TicketService.close_ticket(record_id=pk, **_kw(request)))


class TicketCsat(APIView):
    def post(self, request, pk):
        d = request.data or {}
        return Response(CSATService.submit(
            ticket_record_id=pk, rating=d.get("rating", 0), feedback=d.get("feedback", ""),
            comments=d.get("comments", ""), **_kw(request)), status=201)


class ChangeApprove(APIView):
    def post(self, request, pk):
        _require_admin(request)
        ch = Docs.transition(
            workspace_id=_ws(request), entity_slug="itsm_change", record_id=pk,
            updates={"status": "approved"}, member=_member(request), actor_id=_uid(request),
            event_type="change.approved")
        return Response(ch)


class KnowledgeRecommend(APIView):
    def get(self, request):
        return Response(KnowledgeService.recommend(
            workspace_id=_ws(request), category=request.query_params.get("category", ""),
            keywords=request.query_params.get("q", ""), member=_member(request)))


class SlaDashboard(APIView):
    def get(self, request):
        from apps.sla.services import SLAService
        return Response(SLAService.dashboard(_ws(request)))
