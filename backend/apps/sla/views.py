"""
SLA REST API (PROJECT_HANDBOOK.md §28.4).

Policy + business-hours CRUD, per-record SLA status + pause/resume (the per-record
routes are mounted under ``/api/v1/data/{slug}/{id}/`` from ``apps.records.urls``),
and a workspace SLA health dashboard. Workspace-scoped; writes role-gated.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BusinessHours, SLAPolicy
from .serializers import (
    BusinessHoursSerializer,
    SLAPolicySerializer,
    SLARecordSerializer,
)
from .services import SLAService

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


# ── policies ──────────────────────────────────────────────────────────────────
class PolicyListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = SLAPolicy.objects.filter(workspace_id=_ws(request), deleted_at__isnull=True)
        return Response({"results": SLAPolicySerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = SLAPolicySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if SLAPolicy.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A policy with this slug already exists")
        obj = ser.save(workspace_id=ws)
        return Response(SLAPolicySerializer(obj).data, status=status.HTTP_201_CREATED)


class PolicyDetailView(APIView):
    def _get(self, request, pk):
        obj = SLAPolicy.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Policy not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(SLAPolicySerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        obj = self._get(request, pk)
        ser = SLAPolicySerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(SLAPolicySerializer(obj).data)

    def delete(self, request, pk):
        member = _require_write(request)
        self._get(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── business hours ────────────────────────────────────────────────────────────
class BusinessHoursListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = BusinessHours.objects.filter(workspace_id=_ws(request), deleted_at__isnull=True)
        return Response({"results": BusinessHoursSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = BusinessHoursSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(workspace_id=_ws(request))
        return Response(BusinessHoursSerializer(obj).data, status=status.HTTP_201_CREATED)


class BusinessHoursDetailView(APIView):
    def _get(self, request, pk):
        obj = BusinessHours.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Business hours not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(BusinessHoursSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        obj = self._get(request, pk)
        ser = BusinessHoursSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(BusinessHoursSerializer(obj).data)


# ── per-record (mounted under /api/v1/data/{slug}/{id}/) ──────────────────────
class RecordSLAView(APIView):
    def get(self, request, entity_slug, record_id):
        _member(request)
        records = SLAService.status_for(record_id, _ws(request))
        return Response({"results": SLARecordSerializer(records, many=True).data,
                         "count": len(records)})


class RecordSLAPauseView(APIView):
    def post(self, request, entity_slug, record_id):
        _require_write(request)
        records = SLAService.pause_record(record_id, _ws(request))
        return Response({"paused": len(records),
                         "results": SLARecordSerializer(records, many=True).data})


class RecordSLAResumeView(APIView):
    def post(self, request, entity_slug, record_id):
        _require_write(request)
        records = SLAService.resume_record(record_id, _ws(request))
        return Response({"resumed": len(records),
                         "results": SLARecordSerializer(records, many=True).data})


# ── dashboard ─────────────────────────────────────────────────────────────────
class SLADashboardView(APIView):
    def get(self, request):
        _member(request)
        return Response(SLAService.dashboard(_ws(request)))
