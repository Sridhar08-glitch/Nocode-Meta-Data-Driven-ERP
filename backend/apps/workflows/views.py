"""
Workflow REST API (PROJECT_HANDBOOK.md §21.7).

All endpoints are workspace-scoped (``request.workspace_id``) and require an active
workspace membership. Write/run operations are role-gated (owner/admin/member);
viewers are read-only. The webhook-trigger endpoint additionally requires the
definition to be ``webhook``-triggered and active.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepRun,
)
from .serializers import (
    WorkflowDefinitionSerializer,
    WorkflowEdgeSerializer,
    WorkflowRunSerializer,
    WorkflowStepRunSerializer,
    WorkflowStepSerializer,
)
from .services import WorkflowConcurrencyError, WorkflowService

_WRITE_ROLES = {"owner", "admin", "member"}


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


def _require_write(request):
    m = _member(request)
    if getattr(m, "role", "") not in _WRITE_ROLES:
        raise PermissionDenied("Insufficient role for this action.")
    return m


def _get_def(ws, pk) -> WorkflowDefinition:
    wf = WorkflowDefinition.objects.filter(id=pk, workspace_id=ws).first()
    if wf is None:
        raise NotFound("Workflow not found")
    return wf


# ── definitions ───────────────────────────────────────────────────────────────
class DefinitionListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = WorkflowDefinition.objects.filter(workspace_id=_ws(request))
        if request.query_params.get("trigger_type"):
            qs = qs.filter(trigger_type=request.query_params["trigger_type"])
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        qs = qs.order_by("-created_at")
        return Response({"results": WorkflowDefinitionSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = WorkflowDefinitionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        wf = ser.save(workspace_id=_ws(request))
        return Response(WorkflowDefinitionSerializer(wf).data, status=status.HTTP_201_CREATED)


class DefinitionDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        wf = _get_def(_ws(request), pk)
        return Response(WorkflowDefinitionSerializer(wf).data)

    def patch(self, request, pk):
        _require_write(request)
        wf = _get_def(_ws(request), pk)
        ser = WorkflowDefinitionSerializer(wf, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(WorkflowDefinitionSerializer(wf).data)

    def delete(self, request, pk):
        _require_write(request)
        wf = _get_def(_ws(request), pk)
        wf.status = "archived"
        wf.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class DefinitionActivateView(APIView):
    def post(self, request, pk):
        _require_write(request)
        wf = _get_def(_ws(request), pk)
        wf.status = "active"
        wf.save(update_fields=["status"])
        return Response(WorkflowDefinitionSerializer(wf).data)


class DefinitionPauseView(APIView):
    def post(self, request, pk):
        _require_write(request)
        wf = _get_def(_ws(request), pk)
        wf.status = "paused"
        wf.save(update_fields=["status"])
        return Response(WorkflowDefinitionSerializer(wf).data)


class DefinitionDuplicateView(APIView):
    def post(self, request, pk):
        _require_write(request)
        ws = _ws(request)
        wf = _get_def(ws, pk)
        new_slug = request.data.get("slug") or f"{wf.slug}-copy"
        if WorkflowDefinition.objects.filter(workspace_id=ws, slug=new_slug).exists():
            raise ValidationError(f"slug {new_slug!r} already exists")
        clone = WorkflowDefinition.objects.create(
            workspace_id=ws, name=f"{wf.name} (copy)", slug=new_slug,
            description=wf.description, trigger_type=wf.trigger_type,
            trigger_config=wf.trigger_config, entity_id=wf.entity_id,
            module_id=wf.module_id, status="draft",
            max_concurrent_runs=wf.max_concurrent_runs,
            timeout_seconds=wf.timeout_seconds, retry_policy=wf.retry_policy)
        id_map = {}
        for s in WorkflowStep.objects.filter(workflow_id=wf.id):
            ns = WorkflowStep.objects.create(
                workflow_id=clone.id, workspace_id=ws, step_type=s.step_type,
                name=s.name, config=s.config, position_x=s.position_x,
                position_y=s.position_y, is_entry=s.is_entry, on_error=s.on_error,
                retry_config=s.retry_config)
            id_map[s.id] = ns.id
        for e in WorkflowEdge.objects.filter(workflow_id=wf.id):
            WorkflowEdge.objects.create(
                workflow_id=clone.id, workspace_id=ws,
                source_step_id=id_map.get(e.source_step_id),
                target_step_id=id_map.get(e.target_step_id),
                condition_label=e.condition_label, condition_expr=e.condition_expr)
        return Response(WorkflowDefinitionSerializer(clone).data,
                        status=status.HTTP_201_CREATED)


# ── steps ─────────────────────────────────────────────────────────────────────
class StepListCreateView(APIView):
    def get(self, request, pk):
        _member(request)
        _get_def(_ws(request), pk)
        qs = WorkflowStep.objects.filter(workflow_id=pk).order_by("created_at")
        return Response({"results": WorkflowStepSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request, pk):
        _require_write(request)
        ws = _ws(request)
        _get_def(ws, pk)
        ser = WorkflowStepSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        step = ser.save(workflow_id=uuid.UUID(str(pk)), workspace_id=ws)
        return Response(WorkflowStepSerializer(step).data, status=status.HTTP_201_CREATED)


class StepDetailView(APIView):
    def _get(self, ws, pk, step_id):
        _get_def(ws, pk)
        step = WorkflowStep.objects.filter(id=step_id, workflow_id=pk, workspace_id=ws).first()
        if step is None:
            raise NotFound("Step not found")
        return step

    def get(self, request, pk, step_id):
        _member(request)
        return Response(WorkflowStepSerializer(self._get(_ws(request), pk, step_id)).data)

    def patch(self, request, pk, step_id):
        _require_write(request)
        step = self._get(_ws(request), pk, step_id)
        ser = WorkflowStepSerializer(step, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(WorkflowStepSerializer(step).data)

    def delete(self, request, pk, step_id):
        _require_write(request)
        step = self._get(_ws(request), pk, step_id)
        WorkflowEdge.objects.filter(workflow_id=pk).filter(
            source_step_id=step.id).delete()
        WorkflowEdge.objects.filter(workflow_id=pk).filter(
            target_step_id=step.id).delete()
        step.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── edges ─────────────────────────────────────────────────────────────────────
class EdgeListCreateView(APIView):
    def get(self, request, pk):
        _member(request)
        _get_def(_ws(request), pk)
        qs = WorkflowEdge.objects.filter(workflow_id=pk)
        return Response({"results": WorkflowEdgeSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request, pk):
        _require_write(request)
        ws = _ws(request)
        _get_def(ws, pk)
        ser = WorkflowEdgeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        edge = ser.save(workflow_id=uuid.UUID(str(pk)), workspace_id=ws)
        return Response(WorkflowEdgeSerializer(edge).data, status=status.HTTP_201_CREATED)


class EdgeDetailView(APIView):
    def delete(self, request, pk, edge_id):
        _require_write(request)
        ws = _ws(request)
        _get_def(ws, pk)
        n, _ = WorkflowEdge.objects.filter(id=edge_id, workflow_id=pk, workspace_id=ws).delete()
        if not n:
            raise NotFound("Edge not found")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── runs ──────────────────────────────────────────────────────────────────────
class RunListView(APIView):
    def get(self, request):
        _member(request)
        qs = WorkflowRun.objects.filter(workspace_id=_ws(request))
        if request.query_params.get("workflow_id"):
            qs = qs.filter(workflow_id=request.query_params["workflow_id"])
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        qs = qs.order_by("-created_at")[:200]
        return Response({"results": WorkflowRunSerializer(qs, many=True).data,
                         "count": len(qs)})


class RunDetailView(APIView):
    def get(self, request, run_id):
        _member(request)
        run = WorkflowRun.objects.filter(id=run_id, workspace_id=_ws(request)).first()
        if run is None:
            raise NotFound("Run not found")
        steps = WorkflowStepRun.objects.filter(run_id=run.id).order_by("started_at")
        return Response({**WorkflowRunSerializer(run).data,
                         "step_runs": WorkflowStepRunSerializer(steps, many=True).data})


class RunCancelView(APIView):
    def post(self, request, run_id):
        m = _require_write(request)
        run = WorkflowRun.objects.filter(id=run_id, workspace_id=_ws(request)).first()
        if run is None:
            raise NotFound("Run not found")
        run = WorkflowService.cancel_run(run.id, actor_id=m.user_id)
        return Response(WorkflowRunSerializer(run).data)


class RunRetryView(APIView):
    def post(self, request, run_id):
        m = _require_write(request)
        run = WorkflowRun.objects.filter(id=run_id, workspace_id=_ws(request)).first()
        if run is None:
            raise NotFound("Run not found")
        new_run = WorkflowService.retry_run(run.id, actor_id=m.user_id)
        return Response(WorkflowRunSerializer(new_run).data, status=status.HTTP_201_CREATED)


# ── webhook trigger ───────────────────────────────────────────────────────────
class WorkflowTriggerView(APIView):
    def post(self, request, pk):
        m = _require_write(request)
        ws = _ws(request)
        wf = _get_def(ws, pk)
        if wf.trigger_type != "webhook":
            raise ValidationError("Workflow is not webhook-triggered")
        if wf.status != "active":
            raise ValidationError("Workflow is not active")
        try:
            run = WorkflowService.trigger_workflow(
                workflow_id=wf.id, context={"webhook": request.data},
                workspace_id=ws, initiated_by=m.user_id, trigger_type="webhook")
        except WorkflowConcurrencyError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(WorkflowRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)
