"""
Project Management + PSA REST API (Phase P2.10) at /api/v1/projects/.

Lifecycle actions run as the real workspace member (RBAC/ABAC/RLS apply). The native engines
(cost rollup, financials/EVM, resources, scheduling) are member-readable; cost posting + setup
are admin-gated.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers as S
from .blueprint import PROJECT_OBJECTS
from .models import ProjectCostEntry
from .services import (
    CostRollupService,
    FinancialsService,
    ProjectError,
    ProjectService,
    ResourceService,
    SchedulingService,
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
        ProjectService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Project numbering ready."})


class DocumentCreate(APIView):
    def post(self, request, entity_slug):
        if entity_slug not in PROJECT_OBJECTS:
            return Response({"detail": "Unknown project object."}, status=404)
        rec = ProjectService.create_document(
            entity_slug=entity_slug, data=request.data or {}, **_kw(request))
        return Response(rec, status=201)


def _action(request, record_id, fn):
    return Response(fn(record_id=record_id, **_kw(request)))


class ProjectStart(APIView):
    def post(self, request, pk): return _action(request, pk, ProjectService.start_project)
class ProjectComplete(APIView):
    def post(self, request, pk): return _action(request, pk, ProjectService.complete_project)
class ProjectBudgetApprove(APIView):
    def post(self, request, pk):
        _require_admin(request)
        return _action(request, pk, ProjectService.approve_budget)
class ProjectBaselineView(APIView):
    def post(self, request, pk):
        return Response(S.BaselineSerializer(
            ProjectService.baseline_project(record_id=pk, **_kw(request))).data, status=201)
class TaskComplete(APIView):
    def post(self, request, pk): return _action(request, pk, ProjectService.complete_task)
class MilestoneComplete(APIView):
    def post(self, request, pk): return _action(request, pk, ProjectService.complete_milestone)
class TimesheetApprove(APIView):
    def post(self, request, pk): return _action(request, pk, ProjectService.approve_timesheet)
class ExpenseApprove(APIView):
    def post(self, request, pk): return _action(request, pk, ProjectService.approve_expense)
class ChangeRequestApprove(APIView):
    def post(self, request, pk):
        return _action(request, pk, ProjectService.approve_change_request)
class DeliverableApprove(APIView):
    def post(self, request, pk): return _action(request, pk, ProjectService.approve_deliverable)


# ── native engines ────────────────────────────────────────────────────────────
class CostEntryView(APIView):
    def get(self, request):
        qs = ProjectCostEntry.objects.filter(workspace_id=_ws(request))
        proj = request.query_params.get("project_record_id")
        if proj:
            qs = qs.filter(project_record_id=proj)
        return Response(S.CostEntrySerializer(qs.order_by("-created_at"), many=True).data)

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        entry = CostRollupService.post_cost(
            workspace_id=_ws(request), project_record_id=d.get("project_record_id"),
            source=d.get("source", "other"), amount=d.get("amount", 0),
            description=d.get("description", ""), entry_date=d.get("entry_date"),
            reference=d.get("reference", ""), post_gl=bool(d.get("post_gl", False)),
            actor_id=_uid(request))
        return Response(S.CostEntrySerializer(entry).data, status=201)


class ProjectRollup(APIView):
    def post(self, request, pk):
        return Response(CostRollupService.rollup_project(
            workspace_id=_ws(request), project_record_id=pk, member=_member(request),
            actor_id=_uid(request)))


class ProjectFinancials(APIView):
    def get(self, request, pk):
        try:
            return Response(FinancialsService.project_financials(
                workspace_id=_ws(request), project_record_id=pk, member=_member(request)))
        except ProjectError as exc:
            return Response({"detail": str(exc)}, status=400)


class ProjectScheduleView(APIView):
    def get(self, request, pk):
        return Response(SchedulingService.project_schedule(
            workspace_id=_ws(request), project_record_id=pk, member=_member(request)))


class ResourceUtilization(APIView):
    def get(self, request):
        return Response(ResourceService.workspace_utilization(
            workspace_id=_ws(request), member=_member(request)))


class ResourceCapacity(APIView):
    def get(self, request):
        weekly = float(request.query_params.get("weekly_hours", 40) or 40)
        return Response(ResourceService.workspace_capacity(
            workspace_id=_ws(request), weekly_hours=weekly, member=_member(request)))
