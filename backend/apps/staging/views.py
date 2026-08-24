"""
Import / Export REST API (PROJECT_HANDBOOK.md §29.3) at /api/v1/import/ and /api/v1/export/.

Workspace-scoped; writes role-gated. Import upload is multipart; export download
returns a signed, expiring URL (artifact in document storage).
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExportJob, ImportJob, ImportRow
from .serializers import (
    ExportJobSerializer,
    ImportJobSerializer,
    ImportRowSerializer,
)
from .services import ExportService, ImportError, ImportService

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


def _import_job(request, pk) -> ImportJob:
    job = ImportJob.objects.filter(id=pk, workspace_id=_ws(request)).first()
    if job is None:
        raise NotFound("Import job not found")
    return job


def _run(fn):
    try:
        return fn()
    except ImportError as exc:
        raise ValidationError(str(exc)) from exc


# ── import ────────────────────────────────────────────────────────────────────
class ImportJobListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = ImportJob.objects.filter(workspace_id=_ws(request)).order_by("-created_at")[:200]
        return Response({"results": ImportJobSerializer(qs, many=True).data, "count": len(qs)})

    def post(self, request):
        member = _require_write(request)
        file_obj = request.FILES.get("file")
        if file_obj is None:
            raise ParseError("multipart 'file' is required")
        entity_slug = request.data.get("entity_slug")
        if not entity_slug:
            raise ValidationError("entity_slug is required")
        import json as _json
        mapping = request.data.get("column_mapping")
        if isinstance(mapping, str):
            try:
                mapping = _json.loads(mapping)
            except ValueError as exc:
                raise ValidationError("column_mapping must be valid JSON") from exc
        job = _run(lambda: ImportService.create_job(
            entity_slug=entity_slug, file_obj=file_obj, filename=file_obj.name,
            duplicate_strategy=request.data.get("duplicate_strategy", "skip"),
            initiated_by=member.user_id, workspace_id=_ws(request),
            column_mapping=mapping or None,
            match_field_slug=request.data.get("match_field_slug", "")))
        return Response(ImportJobSerializer(job).data, status=status.HTTP_201_CREATED)


class ImportJobDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        return Response(ImportJobSerializer(_import_job(request, pk)).data)


class ImportJobMappingView(APIView):
    def patch(self, request, pk):
        _require_write(request)
        _import_job(request, pk)
        mapping = request.data.get("column_mapping", request.data)
        job = _run(lambda: ImportService.set_column_mapping(pk, mapping))
        return Response(ImportJobSerializer(job).data)


class ImportJobPreviewView(APIView):
    def get(self, request, pk):
        _member(request)
        _import_job(request, pk)
        rows = ImportService.preview(pk)
        return Response({"results": ImportRowSerializer(rows, many=True).data})


class ImportJobRowsView(APIView):
    def get(self, request, pk):
        _member(request)
        _import_job(request, pk)
        qs = ImportRow.objects.filter(job_id=pk).order_by("row_number")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        qs = qs[:500]
        return Response({"results": ImportRowSerializer(qs, many=True).data, "count": len(qs)})


class ImportJobConfirmView(APIView):
    def post(self, request, pk):
        member = _require_write(request)
        _import_job(request, pk)
        job = _run(lambda: ImportService.confirm_import(pk, member.user_id))
        return Response(ImportJobSerializer(job).data)


class ImportJobCancelView(APIView):
    def post(self, request, pk):
        _require_write(request)
        _import_job(request, pk)
        job = ImportService.cancel(pk)
        return Response(ImportJobSerializer(job).data)


# ── export ────────────────────────────────────────────────────────────────────
class ExportJobListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = ExportJob.objects.filter(workspace_id=_ws(request)).order_by("-created_at")[:200]
        return Response({"results": ExportJobSerializer(qs, many=True).data, "count": len(qs)})

    def post(self, request):
        member = _require_write(request)
        job = ExportService.create_job(
            entity_slug=request.data.get("entity_slug"),
            nql_ast=request.data.get("nql_ast") or request.data.get("nql"),
            format=request.data.get("format", "csv"),
            requested_by=member.user_id, workspace_id=_ws(request),
            include_fields=request.data.get("include_fields") or [])
        return Response(ExportJobSerializer(job).data, status=status.HTTP_201_CREATED)


class ExportJobDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        job = ExportJob.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if job is None:
            raise NotFound("Export job not found")
        return Response(ExportJobSerializer(job).data)


class ExportJobDownloadView(APIView):
    def get(self, request, pk):
        _member(request)
        url = _run(lambda: ExportService.download_url(pk, _ws(request)))
        return Response({"url": url})
