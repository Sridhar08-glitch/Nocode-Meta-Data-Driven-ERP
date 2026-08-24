"""
Revenue Recognition REST API at /api/v1/revenue/.

Creating/cancelling a schedule and running recognition are financial operations → owner/admin gated;
reads available to any member. Workspace-scoped. Package-independent — packages call these or the
``action_recognize_revenue`` workflow step and never re-implement recognition.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RevenueSchedule
from .serializers import RevenueScheduleCreateSerializer, RevenueScheduleSerializer
from .services import RevenueError, RevenueService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Revenue management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class ScheduleList(APIView):
    def get(self, request):
        qs = RevenueSchedule.objects.filter(workspace_id=_ws(request))
        status_f = request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        return Response(RevenueScheduleSerializer(qs.order_by("-created_at")[:500], many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = RevenueScheduleCreateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        try:
            sched = RevenueService.create_schedule(
                workspace_id=_ws(request), actor_id=_uid(request), **ser.validated_data)
        except RevenueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(RevenueScheduleSerializer(sched).data, status=201)


class ScheduleDetail(APIView):
    def get(self, request, pk):
        sched = RevenueSchedule.objects.filter(workspace_id=_ws(request), id=pk).first()
        if sched is None:
            raise PermissionDenied("Schedule not found.")
        return Response(RevenueScheduleSerializer(sched).data)


class ScheduleCancel(APIView):
    def post(self, request, pk):
        _require_admin(request)
        try:
            sched = RevenueService.cancel(
                workspace_id=_ws(request), schedule_id=pk,
                reason=(request.data or {}).get("reason", ""), actor_id=_uid(request))
        except RevenueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(RevenueScheduleSerializer(sched).data)


class RecognizeView(APIView):
    def post(self, request):
        _require_admin(request)
        data = request.data or {}
        return Response(RevenueService.recognize_due(
            workspace_id=_ws(request), schedule_id=data.get("schedule_id"),
            as_of=data.get("as_of"), actor_id=_uid(request)))
